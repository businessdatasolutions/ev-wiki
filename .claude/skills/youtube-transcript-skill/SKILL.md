---
name: youtube-transcript
description: Fetch a YouTube video's metadata and transcript via Playwright and save it as a Markdown file with a YAML front-matter header; optionally save stills of the video's slides and diagrams with Gemini (extract_stills.py), or find only the stills that answer one question, such as the diagram explaining X (search_stills.py). Trigger on any request involving a YouTube URL where the user wants the spoken content as text — "get the transcript", "transcribe this video", "summarize this video" (fetch first, summarize after), or any time captions/subtitles are useful — and on requests to capture a video's slides, diagrams or screenshots, or to find a specific diagram or slide in a video.
---

# youtube-transcript

Drives a real Chromium browser with Playwright to extract a YouTube video's metadata and auto-generated transcript. Works by riding YouTube's own engagement-panel loader instead of hitting the `timedtext` endpoint or the `youtubei/v1/get_transcript` RPC directly — the page's session already has the PoT tokens YouTube now requires, so the data falls out of the DOM.

Output is a Markdown file with a YAML header (all metadata) and a body with chapters interleaved as section headings around the transcript segments.

## When to use

- User shares a YouTube URL and asks for the transcript, captions, or subtitles
- User wants a written record of a talk, podcast, lecture, or interview
- User asks to summarize, quote from, or analyze the spoken content of a video — fetch the transcript first, *then* do the analysis

## Setup (one time)

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

## How to invoke

Two output modes:

**Markdown (default) — for "give me the transcript" requests:**

```bash
python fetch_transcript.py "https://www.youtube.com/watch?v=VIDEO_ID" -o transcript.md
```

**JSON — when the user wants a *clean* transcript and you'll polish it yourself:**

```bash
python fetch_transcript.py "URL" --json > /tmp/raw.json
```

Then read the JSON, fix ASR errors (proper nouns, product names, mistranscribed acronyms, obvious stutters), and write the polished `.md` yourself. This is almost always what you want — auto-captions are noisy and the model does this cleanup well in one pass.

**Language of the transcript (ev-wiki, 2026-10-06): always pass `--sub-lang nl` for a Dutch video.**

```bash
python fetch_transcript.py "URL" --sub-lang nl -o raw/videos/<slug>.md
```

The transcript panel picks its own caption track, and with `hl=en` pinned it takes a creator-uploaded English track when one exists. An Autovisie review with manual tracks in eight languages came back in English that way. `--sub-lang` gets metadata and the asked track in **one yt-dlp call, without a browser** (`fetch_via_ytdlp`): manual before automatic, and an automatic track only in the video's own spoken language, so a machine translation never comes in (`kies_spoor`). The header then carries `transcript_track: {language_code, kind, via: yt-dlp}`. If that fails, the browser path runs as before; then `transcript_track` is absent and the panel's text may be in another language.

**HTTP 429: use the `android_vr` client.** On 2026-10-06 every subtitle URL from yt-dlp's default web client got HTTP 429, for hours and also with `curl_cffi` impersonation, which looked like a rate limit per connection but was not: the `android_vr` player client fetched the same track at once, with full metadata (language, description, chapters, views). `fetch_via_ytdlp` therefore asks `android_vr` first and falls back to the default client, which waits 30 and 90 s on a 429 and retries. yt-dlp reports a failed subtitle download as a message and carries on, without raising, so the function reads yt-dlp's log to see the 429. The `tv`, `mweb` and `web_safari` clients failed on that video ("page needs to be reloaded", "requested format is not available"). A "manual" track is not always human: that Autovisie track was a pasted ASR text ("DON Feng").

**View count is a snapshot.** The header carries `view_count_date:` next to `view_count:`, the day it was read. ev-wiki stores views per measurement on the source page (`weergaven:`), so a later re-read adds a measurement instead of overwriting one.

Other flags: `--headed` (show the browser, useful for debugging consent/sign-in walls), `--timeout MS` (per-step, default 30s).

## Output shape

```markdown
---
title: "Running an AI-native engineering org"
video_id: igO8iyca2_g
url: https://www.youtube.com/watch?v=igO8iyca2_g
channel: Claude
channel_id: UCV03SRZXJEz-hchIAogeJOg
channel_url: https://www.youtube.com/channel/UCV03SRZXJEz-hchIAogeJOg
publish_date: '2026-05-08T11:50:11-07:00'
upload_date: '2026-05-08T11:50:11-07:00'
category: Science & Technology
duration: '28:38'
length_seconds: 1718
view_count: 9179
default_language: en
is_live: false
thumbnail: https://i.ytimg.com/vi/igO8iyca2_g/maxresdefault.jpg
keywords:
  - claude
  - claude code
  - anthropic
caption_tracks:
  - language_code: en
    name: English (auto-generated)
    kind: asr
    is_translatable: true
thumbnails:
  - {url: 'https://i.ytimg.com/vi/igO8iyca2_g/default.jpg', width: 120, height: 90}
  - {url: 'https://i.ytimg.com/vi/igO8iyca2_g/mqdefault.jpg', width: 320, height: 180}
  - ...
chapters:
  - {title: Intro, start: '0:00', start_ms: 0}
  - {title: The shift, start: '2:11', start_ms: 131000}
description: |
  When agentic coding goes from individual tool to org-wide default, the tool isn't
  the hard part... your processes are.
---

## Transcript

[0:00] ...

## [2:11] The shift

[2:11] ...
```

## Metadata fields

| Field | Source | Notes |
|---|---|---|
| `title`, `video_id`, `url` | `videoDetails` | Canonical |
| `channel`, `channel_id`, `channel_url` | `videoDetails.author` / `.channelId` | URL is constructed |
| `publish_date` | `microformat.publishDate` | When YouTube made it visible |
| `upload_date` | `microformat.uploadDate` | When the file was uploaded — usually same as publish but differs for premieres / re-uploads |
| `category` | `microformat.category` | E.g. "Science & Technology", "Music" |
| `duration` / `length_seconds` | `videoDetails.lengthSeconds` | `duration` is a `mm:ss` / `h:mm:ss` string |
| `view_count` | `videoDetails.viewCount` | Precise integer (not the rounded "12K" displayed) |
| `default_language` | `microformat.defaultLanguage` / `defaultAudioLanguage` | Often null — many videos don't set it |
| `is_live`, `is_upcoming`, `is_private`, `is_family_safe` | flags | |
| `thumbnail` | `videoDetails.thumbnail.thumbnails[-1].url` | Highest-resolution single URL |
| `thumbnails` | `videoDetails.thumbnail.thumbnails` | All resolutions (default → maxresdefault), each with width/height |
| `keywords` | `videoDetails.keywords` | Creator-set tags, not always populated |
| `caption_tracks` | `captions.playerCaptionsTracklistRenderer.captionTracks` | Each: `language_code`, `name`, `kind` (`'asr'` for auto-generated, `'manual'` for creator-uploaded), `is_translatable` |
| `available_countries` | `microformat.availableCountries` | ISO country codes; long list — usually omitted from the YAML if empty |
| `chapters` | engagementPanels macroMarkersListRenderer | Each: `title`, `start` (label), `start_ms` |
| `description` | `videoDetails.shortDescription` | The **full** creator-written description (see note below) |

### A note on `description` vs `shortDescription`

- `<meta property="og:description">` returns a truncated ~160-char blurb meant for social-share previews
- `videoDetails.shortDescription` is misleadingly named — it's the **full** creator-written description with all line breaks, links, hashtags, and timestamps preserved
- The DOM element `#description-inline-expander` renders the same content as `shortDescription` but with elements made interactive

This skill uses `shortDescription` and exposes it as `description` in the YAML, with a `|` literal block scalar so multi-line text round-trips cleanly.

### Chapters in the body

When YouTube provides chapters, the script emits each chapter as a `## [mm:ss] Title` heading and groups the transcript segments under it. When there are no chapters, the body is a flat `## Transcript` section.

## Workflow recommendation

1. Run with `--json` to get structured data (metadata + raw segments with timestamps).
2. Read the JSON.
3. ASR-clean the transcript (fix product/people names, drop obvious stutters, light punctuation), preserve timestamps.
4. Build the YAML header from the metadata block as-is and write the final `.md`. The script's own `--md` output is fine as a fallback if you don't need cleaning.

## Visual stills (opt-in)

`extract_stills.py` saves a still of every information-bearing visual in the video (slides, diagrams, charts, tables, code) plus a manifest of what each one shows. Run it after the transcript, for talks, demos and slide-led videos. Skip it for talking-head podcasts, where there is nothing to capture.

```bash
python extract_stills.py "URL" --slug <slug>                      # normal run
python extract_stills.py "URL" --slug <slug> --dry-run > f.json   # Gemini only, writes nothing
python extract_stills.py "URL" --slug <slug> --findings f.json    # re-cut frames, no new Gemini call
```

`<slug>` is the transcript's slug, so the manifest lands next to `raw/videos/<slug>.md`.

**How it works.** Gemini can find and read the visuals but never returns an image. Its output is text with `MM:SS` timestamps, and its `processing_call` / `processing_result` steps carry only IDs and signatures, not the frames it looked at. So the work is split:

1. **Find.** One Gemini call on the YouTube URL (no upload), constrained by a JSON schema. Each item has `start`, `end`, `kind`, `title`, `content` (verbatim on-screen text) and `adds` (what the visual says that the narration doesn't).
2. **Grab.** yt-dlp resolves the ≤1080p stream URL without downloading, and ffmpeg seeks it for one frame per visual at `end − 1s`: slides that build up only gain content, so the last stable frame carries the most. If a seek fails, `FrameSource` downloads the video once into a temp dir and cuts the remaining frames from that copy. The manifest's `extractor.frames` line says which happened.
3. **Dedupe.** Compare 160×90 grayscale thumbnails; a mean absolute difference below 1.0 means the same picture (a slide shown twice). On the Fung talk, repeats scored ≤ 0.24 and distinct slides on the same template scored ≥ 3.50. At 16×16 the text differences vanish, and four distinct slides were dropped.
4. **Land.** Stills go to `raw/images/<slug>/NN-MMmSS-<title>.png` (gitignored). The manifest goes to `raw/videos/<slug>.stills.md` (committed): a YAML header with model, mode and token usage, then one section per still marked *machine-read, unverified*.

Verifying, selecting and publishing the stills happens at Process; see CLAUDE.md §Video stills.

**Credential and model.** The script reads `GEMINI_API_KEY` from the environment, else `GEMINI-API-KEY` from the repo `.env`. The default model is `gemini-3.8-flash`. The `.env`'s `GEMINI-MODEL-ID` (`gemini-3.1-flash-lite-preview`) is not used, because agentic mode supports only 3.8 / 3.7 / 3.6 Flash and 3.5 Flash-Lite, and the measurements below were taken on 3.8 Flash.

### Static vs. agentic (measured 2026-10-01)

In *agentic* video understanding, the model calls `get_transcript`, `get_frames(start, end, fps)` and `get_audio` in a loop. It is pitched as up to 88% cheaper on long videos, and that holds for **targeted** questions. Listing *every* visual is the opposite task:

| Video | Mode | Tokens | Time | Result |
|---|---|---|---|---|
| Gemini explainer, 3:19 | agentic | 653,588 (489k cached) | — | 4 visuals after 15 tool rounds |
| | static, default resolution | 19,680 | 13 s | 3 visuals (two build states merged) |
| | static, `--resolution high` | 59,006 | 13 s | the same 3 visuals |
| Fung talk, 28:38 | agentic | — | 4 m 44 s | **failed**: 400 *"Model generated too many tool calls"* |
| | static, default resolution | 163,151 | 59 s | 30 visuals → 27 stills: **all 12** hand-captured slides, plus 5 content slides the hand-pick missed |
| Google Cloud Tech clinic, 26:07 | static, default resolution | 153,251 | 50 s | 39 visuals → 38 stills: both user-supplied screenshots, and **all 4** definition cards. A pixel scan of every second for the card's border found the same 4 windows and no others |

The clinic run is the case the pipeline exists for. The narration names each term (*"Open telemetry is a standard for the standard"*) and only the card defines it.

So `--mode static` is the default. `--mode agentic` stays available for short videos and for re-testing on newer models. `--resolution high` triples the cost without changing what is found.

### Failure modes (stills)

- **`responseFormat must be set when responseMimeType is set`.** Don't pass `response_mime_type`; the MIME type goes inside `response_format={"type": "text", "mime_type": "application/json", "schema": ...}`.
- **`Cannot send a request, as the client has been closed`.** A temporary `genai.Client()` is collected mid-call. Bind it to a name before calling `.interactions.create`.
- **Agentic `400 Model generated too many tool calls`.** See the table above; use static.
- **yt-dlp warns `n challenge solving failed`.** Harmless so far: 1080p still downloads. If formats actually go missing, install a JS runtime (deno) and enable the challenge solver per the yt-dlp EJS wiki page.
- **Small print is misread.** An on-screen URL came back differently wrong in each mode. That is why Process reads every still itself.
- **Over-reporting.** Section headers and question cards come back as "slides", and a diagram that builds up comes back once per build state (15 items for the four diagrams of a 3-minute explainer). This is expected; Process drops navigation and keeps each diagram's fully built state.
- **Mid-animation frames.** When a display window is very short (about 2 s), `end − 1s` can land while an element is still animating in. Process uses the neighbouring build state instead.
- **Already-ingested video.** Run only this script with the existing slug. Re-running `fetch_transcript.py -o` on that path replaces the curated transcript (see CLAUDE.md §Video stills).

## Targeted still search (opt-in)

`search_stills.py` finds the stills that answer one question, such as *"the diagram on complexity versus complicatedness"*, without paying for the whole video. It is a separate tool. It does not replace `extract_stills.py`, and it never writes over its outputs.

```bash
python search_stills.py "URL" --slug <slug> --query "the diagram explaining X"
python search_stills.py "URL" --slug <slug> --query "..." --locate-only        # windows only, no video calls
python search_stills.py "URL" --slug <slug> --query "..." --windows 6:40-9:10,15:05-16:10 --pad 5
python search_stills.py "URL" --slug <slug> --query "..." --dry-run            # matches as JSON, writes nothing
```

It needs the transcript at `raw/videos/<slug>.md` first (or pass `--transcript PATH`). For a video already in the wiki that file exists; don't re-fetch it.

**How it works.**

1. **Locate.** One text-only Gemini call reads the transcript and proposes up to `--max-windows` (3) passages where the visual is likely on screen, each with a reason. The prompt matches on meaning, because slide labels are often never spoken, and asks for separate passages rather than several windows on the strongest one. Windows are padded (`--pad`, 30 s) and merged. `--windows` skips this step.
2. **Find.** One Gemini video call per window. The YouTube URL goes in with `processing: {"type": "static", "start_offset": "...s", "end_offset": "...s", "fps": 2}`, so only those minutes are sampled, at twice the full scan's rate. The schema is `extract_stills.py`'s plus `match`: why this visual answers the query.
3. **Grab.** As in `extract_stills.py`: seek the stream (download only if a seek fails), one frame per match at `end − 1s`, dedupe.
4. **Fall back**, only when nothing matched: widen the windows (`--widen`, 120 s more each side) and search only the new minutes; then search the whole video. `--no-fallback` stops after the first stage. The manifest records which stage found each still.

**Outputs**, beside the full scan's and never on top of them:
- `raw/images/<slug>/search-<query>/NN-MMmSS-<title>.png` (gitignored)
- `raw/videos/<slug>.search-<query>.stills.md` (manifest: the query, every window searched and why, each match's reason, token usage)

Re-running the same query replaces only that query's folder. `extract_stills.py`'s cleanup only removes `NN-MMmSS-*.png` files at the top of `raw/images/<slug>/`, so it never touches a `search-*` folder. A test pins this.

**Tests.** `python -m unittest discover -s .claude/skills/youtube-transcript-skill/tests`. These are offline tests of the pure parts: transcript parsing, window padding/merging/subtraction, timestamp resolution, output paths and manifest for the search, and the timestamp window for the full scan (`test_extract_stills.py`). The Gemini and ffmpeg steps were checked live, on the run below.

### Measured 2026-10-03: Morieux, *The Social Economics of Productivity* (Talks at Google, 50:31)

Query: *"diagrams on complexity vs complicatedness"*. Baseline: `extract_stills.py --dry-run`, the full static scan, which found 35 visuals for 285,630 tokens. Three are squarely on the query: the build-up of the ×6 complexity / ×35 complicatedness chart (6:43–9:09) and *Managing complexity without getting complicated* (15:11–15:45).

| Run | Windows searched | Stills | Tokens | vs. full scan |
|---|---|---|---|---|
| Located, first prompt | 6:15–9:45 | 5: the ×6/×35 chart, with 3 mid-animation build states | 48,870 | 17% |
| Located, revised prompt | 7:25–9:40 · 10:55–13:25 · 13:45–16:15 | 5: the chart, and *Managing complexity* | 90,142 | 32% |
| Located, revised prompt | 7:25–9:45 · 10:55–13:25 · 25:15–27:05 | 2: the chart only | 82,531 | 29% |
| `--windows` by hand, `--pad 5` | 6:35–9:15 · 15:00–16:15 | 6: both diagrams, every build state | 41,222 | 14% |

- **The central visual was found every time.** Secondary visuals depend on which windows Locate picks, and that varies between runs (the third run spent a window on a COVID passage). Whether Gemini counts a borderline slide as a match also varies: the *"Complicatedness stifles productivity"* series came back as 7 matches in one run and 0 in the next.
- **Gemini reported times as positions in the full video** in every window, not relative to the clip. `resolve_times` handles both and records which one applied.
- **For an exhaustive answer, run a full scan.** A search is cheap and good at "find *the* diagram". It is not a catalogue. When you know roughly where the visual is, `--windows` is cheapest and fully repeatable.

### Failure modes (search)

- **Fractional timestamps.** Gemini sometimes answers `10:55.000`. `fetch_transcript._ts_to_ms` returns **0** for that (its `int()` fails silently), and a whole-number-only pattern rejects it: on 2026-10-03 all 7 matches in a window were dropped as "unparseable". Both scripts now read Gemini's times with `fetch_transcript.ts_seconds()`, which accepts fractions. `_ts_to_ms` keeps its 0-on-failure behaviour, which the chapter logic relies on. The full scan was fixed the same day: on 74 real timestamps from two earlier scans it gives identical results.
- **A visual that starts before its window** is reported from the window's start (e.g. *on screen 7:25–8:34* for a chart up since 6:43). The frame at `end − 1s` is unaffected.
- **Locate is not repeatable.** Same transcript, same query, different windows. Use `--locate-only` to inspect, and `--windows` to pin them.
- **Minutes past 99 (fixed 2026-10-03).** Past an hour, Gemini sometimes writes minutes only: `127:09` for 2:07:09. `ts_seconds()` allowed two-digit minutes, so on an 8-hour stream all 30 matches in two of four windows were skipped as *"timestamps unparseable or outside the window"*. In the other two windows Gemini wrote `h:mm:ss`, which is why the run looked half-successful. `ts_seconds()` now accepts any number of minutes in the `M:SS` form; a test pins it. **The tell:** `NNN:SS` times in the manifest's `## Skipped` list.

## Long videos (multi-hour, measured 2026-10-03)

First run on an 8:01:10 conference livestream (YC Root Access, `T6hVGJ4gepk`, 37 talks). What held, and what to do differently from a normal video:

- **Transcript: use yt-dlp captions, not the panel.** `_scroll_panel` stops after 40 jumps of 150 ms and nothing checks the last timestamp against `length_seconds`, so a multi-hour panel can come back silently truncated. `yt-dlp --skip-download --write-auto-subs --sub-langs en --sub-format vtt` fetched all 3.7 MB in under a second. Then build the file with this skill's own `to_markdown()` so the YAML contract and chapter headings match.
- **VTT parse rule.** Keep the **last line of every real cue** and skip the ~10 ms hold cues. Do not select lines by their inline timing tag: a one-word line (`frontier.`) has no tag, and that test silently dropped 229 lines on this video. Unescape HTML entities (`&gt;&gt;` is the speaker-change marker).
- **Gates before writing:** last segment within 10 min of the end; no gap over 3 min outside known breaks; no doubled `(time, text)` pairs; no a11y-label prefixes.
- **Probe before Gemini.** `ffmpeg -ss <t> -i "$(yt-dlp -g -f <fmt> URL)" -frames:v 1` seeks the stream remotely: 18 frames across 8 hours took 34 s with no download. It showed which talks had slides at all; two stage firesides were dropped before any Gemini call.
- **Stills: one `search_stills.py` run, pinned windows, `--no-fallback`, `--fps 1`.** This run predates stream seeking and downloaded the whole video (3.4 GB) twice to cut 67 frames. Since the same day frames are grabbed by seeking the stream: re-grabbing 8 of those stills that way took about 1 s each, with no download, and every one was pixel-identical to the downloaded cut (thumbnail difference 0.00). Without `--no-fallback`, a window with no match triggers a whole-video call, about 2.7M tokens at the measured ~95 tokens/s. Four windows (39 min) cost 239,294 tokens; re-running two after the fix above cost 79,190. Total ≈ 12% of a full scan.
- **Known, unfixed:** still numbers from 100 up (`100-…png`) escape the cleanup regex `^\d{2}-`; a run that big should be split.

## Failure modes

- **`error: "no transcript section"`** — Video has no captions (common for music videos, very short clips, some unlisted videos). The skill still writes the markdown file with metadata only and a placeholder `## Transcript` section. Exit code is `1` so callers can branch on transcript availability without losing metadata.
- **`error: "transcript panel did not render"`** — Trigger fired but the segment renderers didn't appear in time. Bump `--timeout` to 60000 and retry. If it still fails the video may be region-locked, age-gated, or hitting a panel-render path the skill doesn't handle yet — observed on some long-format talks (≥20 min) even when captions exist; see [GH #2](https://github.com/businessdatasolutions/ai-wiki/issues/2). The skill still writes a metadata-only file.

  *2026-09-15 incident note — the locale trap.* A **third** root cause with the
  same symptom, and the one to check first because it is the cheapest to rule out.
  YouTube picks the interface language from the **request IP**, not from the browser
  context's `locale=`. On a non-English network the watch page renders localized
  button labels — observed: Dutch `"Transcript tonen"` — and every English-text
  matcher in `_trigger_transcript_panel` (`/show transcript/i`) silently fails to
  match. `has_transcript_ui` still returns True (the section renderer exists and is
  language-independent), so the function falls through to the `yt-action` fallback,
  which returns True unconditionally, and `_wait_for_transcript` then times out on a
  panel nothing ever opened. Retrying and raising `--timeout` do not help: the
  failure is deterministic, not flaky.

  **The distinguishing tell is the network, not the DOM:** this cause produces
  **ZERO** `/youtubei/v1/get_transcript` requests, because no trigger ever fired.
  The 2026-05-13 cause produces one with status **400**; the 2026-08-12 cause
  produces one with status **200**. Check the request count before the status.

  Fixed by pinning `hl=en` on the watch URL in `fetch()`. Note that `locale="en-US"`
  on the context and the `navigator.languages` spoof were *already in place* and did
  **not** prevent this — neither overrides YouTube's IP-based language selection, so
  do not treat their presence as evidence the locale is pinned. This is invisible to
  anyone developing from an English-locale network, which is why it survived three
  prior incident investigations.

  *2026-08-12 incident note.* Same symptom, **different root cause** — worth checking before you go down the anti-bot path. `_trigger_transcript_panel` used to fire *both* the `yt-action` event **and** a click on "Show transcript". Because YouTube's button *toggles* the panel, the event opened it and the click immediately closed it again, so `_wait_for_transcript` polled a panel that had been open for ~200 ms. Two of five videos in that batch failed deterministically; `/get_transcript` returned **200**, which is the tell that distinguishes this from the 2026-05-13 case below. Fixed by making the click the primary path and the event a fallback used only when no button exists. Note the failure is *also* mildly flaky on long videos — one of the two needed a retry even after the fix.

  *2026-05-13 incident note.* YouTube's `/youtubei/v1/get_transcript` endpoint started rejecting WebDriver-flagged sessions with HTTP 400 `"Precondition check failed"`, which surfaces in the skill as this same `panel did not render` symptom (the spinner spins forever, the segments never load). The fix is automation-signal masking, not auth: `--disable-blink-features=AutomationControlled` at launch, `navigator.webdriver` overridden to `undefined`, plus a non-`HeadlessChrome` user-agent. All three are now in place in `fetch()`. If you see this symptom return, the diagnostic to confirm it's the same root cause is: `page.on('response', ...)` and look for `/get_transcript` responses with status 400 and a `failedPrecondition` body.
- **Consent or sign-in wall** — Pass `--headed` once, click through manually. For long-term reuse, `BrowserContext.storage_state(path="state.json")` and reload it on subsequent runs.
- **Trusted Types CSP rejection (fixed 2026-05-09, [GH #2](https://github.com/businessdatasolutions/ai-wiki/issues/2))** — YouTube ships a strict CSP that rejects string-form JS evaluation in `wait_for_function` / `evaluate`. The skill registers `bypass_csp=True` on the browser context **and** injects a default Trusted Types policy via `page.add_init_script(...)` (defense in depth). If string-evaluation errors return, verify both are still in place.
- **Every segment appears twice (fixed 2026-08-12)** — another *silent* one. `_extract_segments` queries `ytd-transcript-segment-renderer` page-wide, so when YouTube mounts a second transcript panel the whole list is scraped once per panel and the output is an exact two-fold repeat. The count still looks plausible for the runtime, which is why it survives a glance. `fetch()` now pipes segments through `_dedupe_segments()`, which drops repeated `(timestamp, text)` pairs and keeps first-occurrence order. To check a suspect file: `len(segments)` vs `len({(s['ts'], s['text']) for s in segments})`.

- **All transcript segments land under the last chapter heading (fixed 2026-08-12)** — a *silent* failure: the file looks well-formed, but every chapter heading except the final one is empty. Cause: YouTube dropped `timeRangeStartMillis` from `macroMarkersListItemRenderer`, so `Number(c.timeRangeStartMillis ?? 0)` yielded `0` for every chapter, and `to_markdown`'s boundary filter (`boundaries[i] <= ts < boundaries[i+1]`) became unsatisfiable for all but the last. The scrape now falls back to parsing the human-readable `timeDescription` label (which YouTube renders to the user and therefore drifts far more slowly), and `to_markdown` re-derives any all-zero offsets as defence in depth. **If chapters ever look wrong again, check `start_ms` in the YAML before anything else** — a column of zeros is the signature.

- **Segments start with "1 minute, 2 seconds" and end with "Chapter 3: …" (fixed 2026-10-01)**: silent again. YouTube replaced `ytd-transcript-segment-renderer` with a view-model panel (`transcript-segment-view-model`, chapters as `timeline-chapter-view-model`). The structured path in `_extract_segments` found zero elements and fell through to the `innerText` fallback. That fallback's label filter matched only the older *"N minutes and N seconds"* form, so the panel's hidden a11y label, now comma-joined, stayed in the text: 236 of 251 segments on a 26-minute video. The clean ones were exactly those under a minute and the whole minutes (*"6 minutes"*). Chapter headings were appended to the segment before them. It had been hand-cleaned at acquire twice (HubSpot AEO, 2026-09-30) before anyone traced it. Fixed at the source: `SEGMENT_SELECTOR` covers both tags in all four DOM probes, and the view-model's visible `.ytwTranscriptSegmentViewModelTimestamp` and text span are read directly. As defence in depth, the fallback now filters comma, *and*, hour and Dutch label forms and drops chapter-heading lines. **The tell:** a spoken duration at the start of most segment texts means the structured path missed. Check `document.querySelectorAll(SEGMENT_SELECTOR).length` on the live page before touching the regexes.

- **YouTube DOM drift** — The skill no longer relies on a stable engagement-panel `target-id`; it queries `ytd-transcript-segment-renderer` elements directly anywhere on the page (also fixed in [GH #2](https://github.com/businessdatasolutions/ai-wiki/issues/2)). Metadata is read with optional chaining throughout, so partial drift just nulls a field instead of crashing. If `ytd-transcript-segment-renderer` itself ever gets renamed, the `innerText` fallback on the first expanded engagement panel still works.

## Why not a simpler library?

`youtube-transcript-api` and `yt-dlp` both fetch the `timedtext` endpoint directly. Since 2024, YouTube has been gating that endpoint behind a Proof-of-Origin token tied to a real browser session — so those libraries work intermittently and fail silently (empty 200 responses) on a growing share of videos. Driving a real Chromium with Playwright inherits the session automatically and is the most reliable approach for a "just works" tool inside an agent.

## Why not BeautifulSoup?

Everything useful on a YouTube watch page is JS-rendered, so you have to wait for hydration anyway, and once you've waited, `page.evaluate()` reads from the live DOM more directly than handing HTML to bs4. If you specifically want bs4 in the loop, `await page.content()` gives you the post-hydration HTML string to parse — but for this skill it adds complexity without a payoff.
