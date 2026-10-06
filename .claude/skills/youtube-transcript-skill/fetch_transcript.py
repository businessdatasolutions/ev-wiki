#!/usr/bin/env python3
"""
Fetch a YouTube video's metadata + transcript via Playwright and write a
Markdown file with a YAML front-matter header.

The script drives a real Chromium, expands the description, dispatches
YouTube's `yt-show-engagement-panel-action` event so YouTube's own Polymer
app loads the transcript panel through its internal RPC (which carries the
required PoT / session tokens), then scrapes the resulting DOM.

Metadata is pulled from `window.ytInitialPlayerResponse` and
`window.ytInitialData` once the page has hydrated.

Usage:
    python fetch_transcript.py "https://www.youtube.com/watch?v=VIDEO_ID"
    python fetch_transcript.py "VIDEO_ID" --json
    python fetch_transcript.py "URL" -o transcript.md --headed
"""
from __future__ import annotations

import argparse
import asyncio
import datetime
import html
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yaml
from playwright.async_api import async_playwright, Page


VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

# One element per transcript segment. YouTube replaced the Polymer
# `ytd-transcript-segment-renderer` with a view-model panel
# (`transcript-segment-view-model`) by 2026-10-01. Missing the new tag sent
# every fetch down the innerText fallback in `_extract_segments`, which
# leaked the hidden a11y label ("1 minute, 2 seconds") into 236 of 251
# segments and appended chapter headings to the segment before them. The
# output looked well-formed, so it was hand-cleaned per video instead of
# fixed. See the 2026-10-01 incident note in SKILL.md.
SEGMENT_SELECTOR = "ytd-transcript-segment-renderer, transcript-segment-view-model"


# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------

def extract_video_id(value: str) -> str:
    """Accept a full URL (youtube.com/watch?v=, youtu.be/, /shorts/, /embed/, /live/)
    or a bare 11-char video ID."""
    if VIDEO_ID_RE.match(value):
        return value
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if host == "youtu.be":
        candidate = parsed.path.lstrip("/").split("/")[0]
        if VIDEO_ID_RE.match(candidate):
            return candidate
    if "youtube.com" in host:
        qs = parse_qs(parsed.query)
        if "v" in qs and VIDEO_ID_RE.match(qs["v"][0]):
            return qs["v"][0]
        m = re.search(r"/(?:shorts|embed|v|live)/([A-Za-z0-9_-]{11})", parsed.path)
        if m:
            return m.group(1)
    raise ValueError(f"Could not extract video ID from {value!r}")


# ---------------------------------------------------------------------------
# Page interactions
# ---------------------------------------------------------------------------

async def _dismiss_consent(page: Page) -> None:
    """First-time visitors land on consent.youtube.com. Click 'Reject all' if
    the dialog is present. Best-effort; ignore failures."""
    try:
        for label in ("Reject all", "Alles afwijzen", "Tout refuser", "Alle ablehnen"):
            btn = page.get_by_role("button", name=label)
            if await btn.count() > 0:
                await btn.first.click(timeout=3000)
                await page.wait_for_load_state("domcontentloaded")
                return
    except Exception:
        pass


async def _grab_metadata(page: Page) -> dict:
    """Read the rich metadata blob from ytInitialPlayerResponse + ytInitialData.
    Optional chaining keeps partial DOM-drift from crashing — fields just go null."""
    return await page.evaluate(
        """() => {
            const pr = window.ytInitialPlayerResponse || {};
            const id = window.ytInitialData || {};
            const vd = pr.videoDetails || {};
            const mf = pr.microformat?.playerMicroformatRenderer || {};
            const captionTracks = pr.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];

            // Chapters: walk engagementPanels for the macro-markers list.
            // `timeRangeStartMillis` disappeared from the renderer around
            // 2026-08; the human-readable `timeDescription` label is the stable
            // fallback (it's what YouTube renders to the user). Without this,
            // every chapter scrapes start_ms: 0 and to_markdown() collapses the
            // whole transcript under the last chapter heading — silently.
            const labelToMs = (label) => {
                const parts = String(label || '').trim().split(':').map(Number);
                if (!parts.length || parts.some(Number.isNaN)) return 0;
                return parts.reduce((acc, n) => acc * 60 + n, 0) * 1000;
            };
            let chapters = [];
            for (const panel of (id.engagementPanels || [])) {
                const items = panel?.engagementPanelSectionListRenderer
                    ?.content?.macroMarkersListRenderer?.contents;
                if (items && items.length) {
                    chapters = items
                        .map(c => c.macroMarkersListItemRenderer)
                        .filter(Boolean)
                        .map(c => {
                            const start = c.timeDescription?.simpleText
                                || c.timeDescription?.runs?.[0]?.text || '';
                            const millis = Number(c.timeRangeStartMillis ?? 0);
                            return {
                                title: c.title?.simpleText || c.title?.runs?.[0]?.text || '',
                                start,
                                start_ms: millis || labelToMs(start),
                            };
                        })
                        .filter(c => c.title);
                    break;
                }
            }

            const thumbs = (vd.thumbnail?.thumbnails || []).map(t => ({
                url: t.url, width: t.width, height: t.height,
            }));
            const bestThumb = thumbs.length ? thumbs[thumbs.length - 1].url : null;

            return {
                video_id: vd.videoId || null,
                title: vd.title || null,
                url: `https://www.youtube.com/watch?v=${vd.videoId || ''}`,
                channel: vd.author || null,
                channel_id: vd.channelId || null,
                channel_url: vd.channelId ? `https://www.youtube.com/channel/${vd.channelId}` : null,

                // shortDescription is the FULL creator-written description (not truncated)
                description: vd.shortDescription || null,
                keywords: vd.keywords || [],
                category: mf.category || null,

                publish_date: mf.publishDate || null,    // when YT made it visible
                upload_date: mf.uploadDate || null,      // when the file was uploaded

                length_seconds: Number(vd.lengthSeconds) || null,
                view_count: Number(vd.viewCount) || null,

                default_language: mf.defaultLanguage || mf.defaultAudioLanguage || null,
                available_countries: mf.availableCountries || [],

                is_family_safe: mf.isFamilySafe ?? null,
                is_live: !!vd.isLiveContent,
                is_upcoming: !!vd.isUpcoming,
                is_private: !!vd.isPrivate,

                thumbnail: bestThumb,
                thumbnails: thumbs,

                caption_tracks: captionTracks.map(t => ({
                    language_code: t.languageCode,
                    name: t.name?.simpleText || t.name?.runs?.[0]?.text || null,
                    kind: t.kind || 'manual',     // 'asr' = auto-generated, else creator-uploaded
                    is_translatable: !!t.isTranslatable,
                })),

                chapters,

                playability: {
                    status: pr.playabilityStatus?.status || null,
                    reason: pr.playabilityStatus?.reason || null,
                },
            };
        }"""
    )


async def _transcript_panel_is_open(page: Page) -> bool:
    """True when a transcript panel is already expanded with content in it.

    Checked before every click so a retry never *closes* a panel that a previous
    attempt successfully opened — YouTube's button toggles.
    """
    return await page.evaluate(
        """(sel) => {
            if (document.querySelectorAll(sel).length >= 3) return true;
            for (const p of document.querySelectorAll('ytd-engagement-panel-section-list-renderer')) {
                if (p.getAttribute('visibility') === 'ENGAGEMENT_PANEL_VISIBILITY_EXPANDED'
                    && (p.innerText || '').length > 200) return true;
            }
            return false;
        }""",
        SEGMENT_SELECTOR,
    )


async def _trigger_transcript_panel(page: Page, candidate: int = 0) -> bool:
    """Open the transcript engagement panel. Returns True iff a transcript-bearing
    UI element exists on the page (whether or not the open succeeds — the caller
    waits for content separately).

    YouTube has shipped multiple transcript-panel flavours. The direct click on
    a 'Show transcript' button is the primary path; the legacy `yt-action`
    event-dispatch is the fallback for pages that don't expose one. See GH #2.

    Order matters: YouTube's button *toggles* the panel, so firing both triggers
    unconditionally can open the panel via the event and immediately close it
    via the click. That presents as `transcript panel did not render` even
    though `/youtubei/v1/get_transcript` returned 200 — the 2026-08-12
    BBC/YC ingest hit exactly this.

    `candidate` selects *which* matching button to click. A watch page typically
    carries more than one (observed: two 'Show transcript' buttons plus a
    'Transcript' heading), and the first in DOM order is not reliably the live
    one — clicking a stale or detached node silently does nothing, which is the
    residual flakiness behind the 2026-08-12 four-of-seven failure. The caller
    retries with successive candidates. Indices past the end are a no-op, so an
    over-long retry loop costs nothing.
    """
    has_transcript_ui = await page.evaluate(
        """() => {
            if (document.querySelector('ytd-video-description-transcript-section-renderer')) return true;
            const btn = Array.from(document.querySelectorAll('button')).find(
                b => /show transcript/i.test(b.innerText || '')
            );
            return !!btn;
        }"""
    )
    if not has_transcript_ui:
        return False
    # Never click when a panel is already open — the click would toggle it shut.
    if await _transcript_panel_is_open(page):
        return True
    # Primary: direct click on a 'Show transcript' button. Robust to panel-
    # target-id drift; the click expands whichever panel YouTube currently uses.
    clicked = await page.evaluate(
        """(i) => {
            const btns = Array.from(document.querySelectorAll('button')).filter(
                b => /show transcript/i.test(b.innerText || '')
            );
            if (!btns.length) return false;
            const btn = btns[i % btns.length];
            btn.scrollIntoView({block: 'center'});
            btn.click();
            return true;
        }""",
        candidate,
    )
    if clicked:
        return True
    # Fallback: YouTube's own engagement-panel action, for pages that mount the
    # transcript section without an accompanying 'Show transcript' button.
    await page.evaluate(
        """() => {
            const sec = document.querySelector('ytd-video-description-transcript-section-renderer');
            if (sec && sec.data) {
                const cmd = sec.data.primaryButton?.buttonRenderer?.command;
                const targetId = cmd?.commandExecutorCommand?.commands?.[0]
                    ?.showEngagementPanelEndpoint?.identifier?.tag || 'PAmodern_transcript_view';
                document.dispatchEvent(new CustomEvent('yt-action', {
                    bubbles: true,
                    detail: {
                        actionName: 'yt-show-engagement-panel-action',
                        args: [{ panelIdentifier: targetId }],
                    },
                }));
            }
        }"""
    )
    return True


async def _wait_for_transcript(page: Page, timeout_ms: int) -> None:
    """Wait until transcript content is loaded — segment renderers preferred,
    falling back to any expanded engagement-panel with substantial text."""
    await page.wait_for_function(
        """(sel) => {
            const renderers = document.querySelectorAll(sel);
            if (renderers.length >= 3) return true;
            const panels = document.querySelectorAll('ytd-engagement-panel-section-list-renderer');
            for (const p of panels) {
                if (p.getAttribute('visibility') === 'ENGAGEMENT_PANEL_VISIBILITY_EXPANDED'
                    && (p.innerText || '').length > 200) {
                    return true;
                }
            }
            return false;
        }""",
        arg=SEGMENT_SELECTOR,
        timeout=timeout_ms,
    )


async def _scroll_panel(page: Page) -> None:
    """For long videos the segment list virtualizes. Scroll the segment-renderer
    container to the bottom repeatedly so all segments materialize, then back to
    the top."""
    await page.evaluate(
        """async (sel) => {
            const renderer = document.querySelector(sel);
            if (!renderer) return;
            // Walk up the ancestry to find the scrollable container.
            let scroller = renderer.parentElement;
            while (scroller) {
                if (scroller.scrollHeight > scroller.clientHeight + 50 && scroller.clientHeight > 100) {
                    break;
                }
                scroller = scroller.parentElement;
            }
            if (!scroller) return;
            for (let i = 0; i < 40; i++) {
                const before = scroller.scrollTop;
                scroller.scrollTop = scroller.scrollHeight;
                await new Promise(r => setTimeout(r, 150));
                if (scroller.scrollTop === before) break;
            }
            scroller.scrollTop = 0;
        }""",
        SEGMENT_SELECTOR,
    )


async def _extract_segments(page: Page) -> list[dict]:
    return await page.evaluate(
        """(sel) => {
            // Preferred: query structured segment elements anywhere on the page.
            // Each selector pair is legacy renderer first, then the view-model
            // panel. In the view model, `...Timestamp` is the visible "1:02";
            // its sibling `...TimestampA11yLabel` ("1 minute, 2 seconds") is a
            // different class token, so it never matches here.
            const renderers = document.querySelectorAll(sel);
            if (renderers.length) {
                return Array.from(renderers).map(r => ({
                    ts: (r.querySelector('.segment-timestamp, .ytwTranscriptSegmentViewModelTimestamp')?.innerText || '').trim(),
                    text: (r.querySelector('.segment-text, yt-formatted-string.segment-text, .ytAttributedStringHost')?.innerText || '').trim(),
                })).filter(s => s.text);
            }
            // Fallback: parse innerText of the first expanded engagement panel.
            let panel = null;
            for (const p of document.querySelectorAll('ytd-engagement-panel-section-list-renderer')) {
                if (p.getAttribute('visibility') === 'ENGAGEMENT_PANEL_VISIBILITY_EXPANDED'
                    && (p.innerText || '').length > 200) {
                    panel = p; break;
                }
            }
            if (!panel) return [];
            const lines = (panel.innerText || '').split('\\n').map(s => s.trim()).filter(Boolean);
            const tsRe = /^\\d+:\\d{2}(?::\\d{2})?$/;
            // The timestamp's hidden a11y label is its own line: "6 minutes",
            // "1 minute, 2 seconds", "1 hour, 2 minutes, 3 seconds". Older
            // pages joined the parts with "and", Dutch pages with "en". The
            // 2026-10-01 view-model panel uses commas, which the previous
            // and-only pattern missed, so the label leaked into the text.
            const durRe = /^\\d+\\s+(?:hours?|minutes?|seconds?|uur|minu(?:ut|ten)|seconden?)(?:(?:,|\\s+and|\\s+en)\\s+\\d+\\s+(?:hours?|minutes?|seconds?|uur|minu(?:ut|ten)|seconden?))*$/i;
            // Chapter headings sit between segments in the same panel; the
            // markdown renderer builds chapters from metadata instead.
            const chapterRe = /^(?:Chapter|Hoofdstuk)\\s+\\d+:\\s/;
            const out = [];
            for (let i = 0; i < lines.length; i++) {
                if (!tsRe.test(lines[i])) continue;
                const ts = lines[i];
                const parts = [];
                let j = i + 1;
                while (j < lines.length && !tsRe.test(lines[j])) {
                    if (!durRe.test(lines[j]) && !chapterRe.test(lines[j])) parts.push(lines[j]);
                    j++;
                }
                if (parts.length) out.push({ ts, text: parts.join(' ') });
                i = j - 1;
            }
            return out;
        }""",
        SEGMENT_SELECTOR,
    )


def _dedupe_segments(segments: list[dict]) -> list[dict]:
    """Drop repeated (timestamp, text) pairs, keeping first-occurrence order.

    `_extract_segments` queries `ytd-transcript-segment-renderer` page-wide, so
    when YouTube mounts more than one transcript panel every segment is
    collected once per panel — observed 2026-08-12 on a chaptered talk that came
    back as an exact two-fold repeat of itself. The duplication is silent: the
    segment count still looks plausible for the runtime.

    Deduping on the pair (not on text alone) is lossless: a phrase genuinely
    said twice carries a different timestamp, so an identical pair is by
    construction the same segment rendered twice.

    The key is whitespace-normalized because the two panels line-break the same
    caption differently ("…as it is SaaS or traditional" vs "…as it is SaaS\\nor
    traditional"), so byte-equality misses most of the duplicates. The retained
    text is the first occurrence, verbatim.
    """
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for s in segments:
        key = (s.get("ts", ""), " ".join(s.get("text", "").split()))
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


# ---------------------------------------------------------------------------
# Top-level fetch
# ---------------------------------------------------------------------------

async def fetch(video_id: str, *, headless: bool = True, timeout_ms: int = 30000) -> dict:
    # `hl=en` pins the UI language. Context `locale=` alone is NOT enough:
    # YouTube geolocates the interface language from the request IP, so a
    # non-English network serves localized labels ("Transcript tonen") that
    # the English-text button matchers below cannot match. That presents as
    # `transcript panel did not render` with ZERO /get_transcript calls —
    # the tell that distinguishes it from the 2026-05-13 and 2026-08-12
    # incidents. See the 2026-09-15 incident note in SKILL.md.
    url = f"https://www.youtube.com/watch?v={video_id}&hl=en"
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            # Suppress the Chromium-level automation flag that lets sites detect
            # WebDriver via Blink's runtime signals. Pair with the navigator
            # spoofing in the init script below — YouTube's /youtubei/v1/get_transcript
            # endpoint started rejecting WEBDRIVER-flagged sessions (HTTP 400
            # "Precondition check failed") around 2026-05-13.
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = await browser.new_context(
            locale="en-US",
            viewport={"width": 1280, "height": 900},
            bypass_csp=True,
            # The default Playwright UA contains "HeadlessChrome", which is a
            # secondary anti-bot signal. Pinning to a stable non-headless string
            # avoids that without needing the Chromium version to stay in lockstep.
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/139.0.7258.66 Safari/537.36"
            ),
        )
        # Init scripts run before any YouTube JS, so the spoofs are in place
        # when get_transcript's preflight runs. See GH #2 / 2026-05-13 incident.
        await ctx.add_init_script(
            """
            // Mask navigator.webdriver — the primary automation signal YouTube
            // checks before issuing /youtubei/v1/get_transcript.
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined, configurable: true });
            // Make navigator.plugins look populated (headless reports 0).
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            // Realistic languages array (headless Chrome ships with just one).
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            // chrome.runtime stub: headless Chromium omits window.chrome.
            window.chrome = window.chrome || { runtime: {} };
            // Notifications permission: headless reports 'denied', real Chrome 'default'.
            const origPerm = navigator.permissions && navigator.permissions.query
                ? navigator.permissions.query.bind(navigator.permissions)
                : null;
            if (origPerm) {
                navigator.permissions.query = (p) =>
                    p && p.name === 'notifications'
                        ? Promise.resolve({ state: Notification.permission })
                        : origPerm(p);
            }
            """
        )
        page = await ctx.new_page()
        # Defense-in-depth: register a default Trusted Types policy so string-form
        # JS predicates passed to wait_for_function / evaluate aren't rejected
        # if bypass_csp is ever removed (see GH #2).
        await page.add_init_script(
            """
            if (window.trustedTypes && window.trustedTypes.createPolicy) {
                try {
                    window.trustedTypes.createPolicy('default', {
                        createScript: (s) => s,
                        createScriptURL: (s) => s,
                        createHTML: (s) => s,
                    });
                } catch (e) { /* policy already exists; fine */ }
            }
            """
        )
        page.set_default_timeout(timeout_ms)
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await _dismiss_consent(page)
            await page.wait_for_selector("ytd-watch-flexy", timeout=timeout_ms)
            # Wait for the player to mount so ytInitialPlayerResponse is populated.
            await page.wait_for_selector("video", timeout=timeout_ms)

            # Expand the description so the transcript section element is mounted.
            try:
                await page.click("#expand", timeout=4000)
            except Exception:
                pass

            metadata = await _grab_metadata(page)

            # Retry across the page's several 'Show transcript' buttons: the
            # first in DOM order is not reliably the live one, and a click on a
            # stale node fails silently. Each attempt re-checks whether a panel
            # is already open before clicking, so a retry can never toggle shut
            # a panel an earlier attempt opened. Budget is split across attempts
            # so total wall-clock stays within the caller's timeout.
            attempts = 3
            per_attempt = max(8000, timeout_ms // attempts)
            last_error: Exception | None = None
            for attempt in range(attempts):
                triggered = await _trigger_transcript_panel(page, candidate=attempt)
                if not triggered:
                    return {
                        "video_id": video_id,
                        "metadata": metadata,
                        "transcript": None,
                        "error": "no transcript section (video has no captions or hasn't been processed)",
                    }
                try:
                    await _wait_for_transcript(page, per_attempt)
                    break
                except Exception as e:
                    last_error = e
            else:
                return {
                    "video_id": video_id,
                    "metadata": metadata,
                    "transcript": None,
                    "error": f"transcript panel did not render after {attempts} attempts: {last_error}",
                }

            await _scroll_panel(page)
            segments = _dedupe_segments(await _extract_segments(page))
            return {"video_id": video_id, "metadata": metadata, "transcript": segments}
        finally:
            await browser.close()


# ---------------------------------------------------------------------------
# Caption track in a chosen language (yt-dlp)
# ---------------------------------------------------------------------------
#
# The transcript panel picks its own track. With `hl=en` pinned (see fetch()),
# a video that carries a creator-uploaded English track gets that one, even
# when the video is spoken in Dutch: on 2026-10-06 an Autovisie review with
# manual tracks in eight languages came back in English. `--sub-lang` fetches
# the track in the asked language with yt-dlp instead, manual before automatic,
# and keeps the panel only for metadata.

_VTT_TIME = re.compile(r"^(\d+):(\d{2}):(\d{2})\.(\d{3})\s+-->\s+(\d+):(\d{2}):(\d{2})\.(\d{3})")
_VTT_TAG = re.compile(r"<[^>]+>")


def _vtt_to_segments(vtt: str, rolling: bool) -> list[dict]:
    """Parse WebVTT into panel-shaped segments ({ts, text}).

    `rolling=True` is YouTube's automatic track: each cue repeats the previous
    line and adds one, so keep only the last line of every real cue and skip
    the ~10 ms hold cues. A manual track has whole cues: keep every line.
    """
    # A cue starts at its timing line and runs to the next timing line. Do not
    # split on blank lines: YouTube's automatic track puts a line holding one
    # space inside a cue, and a blank-line split cut the cue's text off its
    # timing (2026-10-06: whole sentences of an ANWB review went missing).
    cues: list[tuple[re.Match, list[str]]] = []
    for line in vtt.replace("\r", "").split("\n"):
        m = _VTT_TIME.match(line)
        if m:
            cues.append((m, []))
        elif cues:
            cues[-1][1].append(line)
    out: list[dict] = []
    for m, raw_lines in cues:
        h, mi, s, ms, h2, mi2, s2, ms2 = (int(x) for x in m.groups())
        start = h * 3600 + mi * 60 + s + ms / 1000
        end = h2 * 3600 + mi2 * 60 + s2 + ms2 / 1000
        text_lines = [html.unescape(_VTT_TAG.sub("", l)).replace("\xa0", " ").strip() for l in raw_lines]
        text_lines = [l for l in text_lines if l]
        if not text_lines:
            continue
        if rolling:
            if end - start < 0.05:
                continue
            text = text_lines[-1]
        else:
            text = " ".join(text_lines)
        sec = int(start)
        ts = f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"
        out.append({"ts": ts, "text": " ".join(text.split())})
    return _dedupe_segments(out)


# YouTube answers HTTP 429 after a burst of subtitle requests (2026-10-06: two of ten
# videos in the first ev-wiki collector run). Waiting usually clears it.
SUBS_RETRY_WAITS_S = (30, 90)


def kies_spoor(info: dict, lang: str) -> str | None:
    """Which track to take for `lang`: 'manual', 'asr', or None.

    A creator-uploaded track in `lang` wins. YouTube also offers an automatic
    track in every language, machine-translated from the spoken one, so an
    automatic track only counts when the video itself is in `lang`: asking an
    English video for `nl` must not return a translation.
    """
    if lang in (info.get("subtitles") or {}):
        return "manual"
    spoken = (info.get("language") or "").split("-")[0]
    auto = info.get("automatic_captions") or {}
    if spoken == lang and (lang in auto or f"{lang}-orig" in auto):
        return "asr"
    return None


def metadata_from_ytdlp(info: dict) -> dict:
    """yt-dlp's info dict in the shape the page scrape produces (see _grab_metadata)."""
    def iso(ts: int | None, ymd: str | None) -> str | None:
        if ts:
            return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).isoformat()
        return f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}" if ymd and len(ymd) == 8 else None

    published = iso(info.get("release_timestamp") or info.get("timestamp"), info.get("upload_date"))
    tracks = [{"language_code": k, "name": None, "kind": "manual", "is_translatable": True}
              for k in (info.get("subtitles") or {}) if k != "live_chat"]
    spoken = info.get("language")
    if spoken and spoken.split("-")[0] in {k.split("-")[0] for k in (info.get("automatic_captions") or {})}:
        tracks.append({"language_code": spoken, "name": None, "kind": "asr", "is_translatable": True})
    chapters = [{"title": c.get("title") or "", "start": _format_duration(int(c.get("start_time") or 0)),
                 "start_ms": int((c.get("start_time") or 0) * 1000)} for c in info.get("chapters") or []]
    thumbs = [{"url": t["url"], "width": t.get("width"), "height": t.get("height")}
              for t in info.get("thumbnails") or [] if t.get("width")]
    return {
        "video_id": info.get("id"),
        "title": info.get("title"),
        "url": f"https://www.youtube.com/watch?v={info.get('id')}",
        "channel": info.get("channel") or info.get("uploader"),
        "channel_id": info.get("channel_id"),
        "channel_url": f"https://www.youtube.com/channel/{info['channel_id']}" if info.get("channel_id") else None,
        "description": info.get("description"),
        "keywords": info.get("tags") or [],
        "category": (info.get("categories") or [None])[0],
        "publish_date": published,
        "upload_date": published,
        "length_seconds": info.get("duration"),
        "view_count": info.get("view_count"),
        "default_language": spoken,
        "is_family_safe": info.get("age_limit", 0) == 0,
        "is_live": bool(info.get("is_live")),
        "thumbnail": info.get("thumbnail"),
        "thumbnails": thumbs,
        "caption_tracks": tracks,
        "chapters": chapters,
    }


def fetch_via_ytdlp(video_id: str, lang: str) -> dict | None:
    """Metadata and the `lang` transcript in one yt-dlp call, no browser.

    Two requests per video instead of the browser path's four to six (page,
    panel, get_transcript, and two yt-dlp runs for manual and automatic). That
    matters because YouTube rate-limits per connection (HTTP 429), and the
    collector fetches several videos a night. Returns None when yt-dlp fails or
    there is no usable track, so the caller can fall back to the browser.
    """
    import yt_dlp  # only this path needs it

    class _Log:
        """yt-dlp reports a failed subtitle download as an error message and carries
        on; it does not raise. Collect the messages to see a 429 (2026-10-06)."""
        def __init__(self):
            self.msgs: list[str] = []
        def debug(self, m): pass
        def info(self, m): pass
        def warning(self, m): self.msgs.append(m)
        def error(self, m): self.msgs.append(m)

    url = f"https://www.youtube.com/watch?v={video_id}"
    with tempfile.TemporaryDirectory() as tmp:
        info, files = None, []
        for wait in (0, *SUBS_RETRY_WAITS_S):
            if wait:
                print(f"warning: HTTP 429 from YouTube, retrying in {wait} s", file=sys.stderr)
                time.sleep(wait)
            log = _Log()
            opts = {"skip_download": True, "writesubtitles": True, "writeautomaticsub": True,
                    "subtitleslangs": [lang], "subtitlesformat": "vtt", "quiet": True,
                    "logger": log, "outtmpl": str(Path(tmp) / "s.%(ext)s")}
            try:
                with yt_dlp.YoutubeDL(opts) as y:
                    info = y.extract_info(url, download=True)
            except yt_dlp.utils.DownloadError as e:
                log.msgs.append(str(e))
            files = sorted(Path(tmp).glob(f"s.{lang}*.vtt"))
            if files or not any("429" in m for m in log.msgs):
                break
        if info is None:
            print(f"warning: yt-dlp failed: {(log.msgs or ['?'])[-1]}", file=sys.stderr)
            return None
        kind = kies_spoor(info, lang)
        if not kind or not files:
            return None
        segs = _vtt_to_segments(files[0].read_text(encoding="utf-8"), rolling=(kind == "asr"))
        if not segs:
            return None
        meta = metadata_from_ytdlp(info)
        meta["transcript_track"] = {"language_code": lang, "kind": kind, "via": "yt-dlp"}
        return {"video_id": video_id, "metadata": meta, "transcript": segs}


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def _ts_to_ms(ts: str) -> int:
    """Convert "mm:ss" or "h:mm:ss" to milliseconds."""
    parts = ts.split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return 0
    if len(nums) == 2:
        return (nums[0] * 60 + nums[1]) * 1000
    if len(nums) == 3:
        return (nums[0] * 3600 + nums[1] * 60 + nums[2]) * 1000
    return 0


# Gemini's timestamps: M:SS or H:MM:SS, sometimes with fractional seconds
# ("10:55.000"), and past an hour sometimes as minutes only ("127:09" for
# 2:07:09). _ts_to_ms returns 0 for those, and its 0-on-failure is relied
# on by the chapter logic, so Gemini's output gets this parser instead.
GEMINI_TS_RE = re.compile(r"^(?:(\d{1,2}):)?(\d+):(\d{2}(?:\.\d+)?)$")


def ts_seconds(ts: str) -> float | None:
    """Seconds for an "M:SS[.fff]" or "H:MM:SS[.fff]" timestamp, or None."""
    m = GEMINI_TS_RE.match((ts or "").strip())
    if not m:
        return None
    hours, minutes, secs = m.groups()
    return int(hours or 0) * 3600 + int(minutes) * 60 + float(secs)


def _format_duration(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class _YtDumper(yaml.SafeDumper):
    """Local Dumper so our str representer doesn't leak globally."""


def _str_representer(dumper, data: str):
    # Use literal block scalar for any multi-line string (description, etc.)
    if "\n" in data:
        # Normalize CRLF -> LF so '|' renders cleanly.
        data = data.replace("\r\n", "\n").replace("\r", "\n")
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_YtDumper.add_representer(str, _str_representer)


# Field order for the YAML header — readable, scannable, with `description` last
# because it's the longest free-text field.
_YAML_KEY_ORDER = [
    "title",
    "video_id",
    "url",
    "channel",
    "channel_id",
    "channel_url",
    "publish_date",
    "upload_date",
    "category",
    "duration",
    "length_seconds",
    "view_count",
    "view_count_date",
    "default_language",
    "is_live",
    "is_upcoming",
    "is_private",
    "is_family_safe",
    "thumbnail",
    "keywords",
    "caption_tracks",
    "available_countries",
    "thumbnails",
    "chapters",
    "description",
]


def _build_yaml_header(meta: dict) -> str:
    enriched = dict(meta)
    if enriched.get("length_seconds"):
        enriched["duration"] = _format_duration(int(enriched["length_seconds"]))

    ordered = {}
    for k in _YAML_KEY_ORDER:
        v = enriched.get(k)
        if v in (None, "", []):
            continue
        ordered[k] = v
    # Append any unexpected fields at the end so we don't silently drop data.
    for k, v in enriched.items():
        if k not in ordered and v not in (None, "", []):
            ordered[k] = v

    return yaml.dump(
        ordered,
        Dumper=_YtDumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=100,
    ).rstrip()


def to_markdown(result: dict) -> str:
    meta = result.get("metadata") or {}
    segments = result.get("transcript") or []
    chapters = meta.get("chapters") or []
    # Defence in depth against the `timeRangeStartMillis` drift (see _grab_metadata):
    # if the scrape produced all-zero offsets, recover them from the labels rather
    # than emitting a file with every segment under the final chapter heading.
    for ch in chapters:
        if not ch.get("start_ms") and ch.get("start"):
            ch["start_ms"] = _ts_to_ms(ch["start"])
    chapters = sorted(chapters, key=lambda c: c.get("start_ms", 0))

    out: list[str] = ["---", _build_yaml_header(meta), "---", ""]

    if not segments:
        out += ["## Transcript", "", "_(no transcript segments returned)_"]
        return "\n".join(out).rstrip() + "\n"

    if not chapters:
        out += ["## Transcript", ""]
        out += [f"[{s['ts']}] {s['text']}" for s in segments]
        return "\n".join(out).rstrip() + "\n"

    # Chapter-aware rendering: each chapter becomes a section heading.
    boundaries = [c.get("start_ms", 0) for c in chapters] + [10**12]
    pre = [s for s in segments if _ts_to_ms(s["ts"]) < boundaries[0]]
    if pre:
        out += ["## Transcript", ""]
        out += [f"[{s['ts']}] {s['text']}" for s in pre]
        out.append("")
    for i, ch in enumerate(chapters):
        chunk = [s for s in segments if boundaries[i] <= _ts_to_ms(s["ts"]) < boundaries[i + 1]]
        label = ch.get("start") or ""
        title = ch.get("title") or f"Chapter {i + 1}"
        heading = f"## [{label}] {title}".strip() if label else f"## {title}"
        out += [heading, ""]
        out += [f"[{s['ts']}] {s['text']}" for s in chunk]
        out.append("")

    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

async def _main() -> int:
    ap = argparse.ArgumentParser(description="Fetch a YouTube video's transcript via Playwright.")
    ap.add_argument("url", help="YouTube URL or 11-char video ID")
    ap.add_argument("-o", "--output", help="Output Markdown path (default: ./<video_id>.md)")
    ap.add_argument("--json", action="store_true", help="Emit raw JSON to stdout instead of Markdown")
    ap.add_argument("--headed", action="store_true", help="Run with a visible browser window")
    ap.add_argument("--timeout", type=int, default=30000, help="Per-step timeout in ms (default: 30000)")
    ap.add_argument("--sub-lang", help="Take the transcript from this caption language via yt-dlp "
                    "(manual before automatic), e.g. nl. Metadata still comes from the page.")
    args = ap.parse_args()

    try:
        video_id = extract_video_id(args.url)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    # With --sub-lang, yt-dlp alone first: no browser, two requests. The browser
    # path stays as the fallback, and then its panel transcript is kept, which
    # may be in another language (check transcript_track at Process).
    result = fetch_via_ytdlp(video_id, args.sub_lang) if args.sub_lang else None
    if result is None:
        if args.sub_lang:
            print(f"warning: no {args.sub_lang} track via yt-dlp; falling back to the browser panel", file=sys.stderr)
        result = await fetch(video_id, headless=not args.headed, timeout_ms=args.timeout)

    # view_count is a snapshot: without the day it was read, two counts of the
    # same video cannot be compared (ev-wiki stores views per measurement).
    if result.get("metadata", {}).get("view_count") is not None:
        result["metadata"]["view_count_date"] = datetime.date.today().isoformat()

    if args.json:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0 if result.get("transcript") else 1

    # Even when no transcript is available (no captions, timeout, panel never
    # rendered), write the markdown file with full metadata + a placeholder
    # transcript section so the metadata isn't lost. Exit code reflects whether
    # the transcript was successfully fetched.
    out_path = Path(args.output) if args.output else Path(f"{video_id}.md")
    out_path.write_text(to_markdown(result), encoding="utf-8")

    if not result.get("transcript"):
        err = result.get("error", "no transcript")
        n_chs = len(result.get("metadata", {}).get("chapters") or [])
        print(
            f"wrote {out_path} (metadata only — {err}; {n_chs} chapters)",
            file=sys.stderr,
        )
        return 1

    n_segs = len(result["transcript"])
    n_chs = len(result["metadata"].get("chapters") or [])
    print(f"wrote {out_path} ({n_segs} segments, {n_chs} chapters)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
