#!/usr/bin/env python3
"""
Find the stills that answer one question about a YouTube video, such as "the
diagram on complexity versus complicatedness", without scanning the whole video.

extract_stills.py catalogues every visual and pays Gemini for every second of
the video. This script spends almost nothing on the parts that don't matter:

    1. Locate  Gemini reads the local transcript (text, cheap) and proposes the
               few windows where the visual is most likely on screen. Or pass
               --windows to set them by hand. Each window is padded and merged.
    2. Find    One Gemini video call per window, using start_offset/end_offset,
               so only those minutes are sampled, at a higher frame rate.
    3. Grab    yt-dlp + ffmpeg cut one frame per match, as in extract_stills.py.
    4. Fall back  If nothing matches: widen the windows once, then search the
               whole video. The manifest records which stage found each still.

Acquire-phase only. Writes beside, never over, extract_stills.py's outputs:
    raw/images/<slug>/search-<query>/NN-MMmSS-<title>.png   (gitignored)
    raw/videos/<slug>.search-<query>.stills.md               (manifest)

Usage:
    python search_stills.py URL --slug <slug> --query "the diagram explaining X"
    python search_stills.py URL --slug <slug> --query "..." --windows 3:20-4:20,12:00-13:00
    python search_stills.py URL --slug <slug> --query "..." --locate-only
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

from fetch_transcript import _format_duration, _ts_to_ms, ts_seconds

SEGMENT_RE = re.compile(r"^\[(\d{1,2}:\d{2}(?::\d{2})?)\] (.+)$")
RANGE_RE = re.compile(r"^\s*(\d{1,2}:\d{2}(?::\d{2})?)\s*-\s*(\d{1,2}:\d{2}(?::\d{2})?)\s*$")


# ---------------------------------------------------------------------------
# Pure helpers (offline-tested in tests/test_search_stills.py)
# ---------------------------------------------------------------------------

def parse_transcript(text: str) -> tuple[dict, list[tuple[float, str]]]:
    """(YAML header, [(seconds, text), ...]) from a raw/videos/<slug>.md file."""
    import yaml

    header: dict = {}
    body = text
    if text.startswith("---\n"):
        _, head, body = text.split("---\n", 2)
        header = yaml.safe_load(head) or {}
    segments = []
    for line in body.splitlines():
        m = SEGMENT_RE.match(line.strip())
        if m:
            segments.append((_ts_to_ms(m.group(1)) / 1000, m.group(2).strip()))
    return header, segments


def transcript_for_prompt(segments: list[tuple[float, str]]) -> str:
    return "\n".join(f"[{_format_duration(int(s))}] {t}" for s, t in segments)


def pad_and_merge(windows: list[dict], *, pad: float, duration: float) -> list[dict]:
    """Pad each window, clamp it to the video, sort, and merge any that overlap."""
    padded = sorted(
        (w | {"start": max(0.0, w["start"] - pad), "end": min(duration, w["end"] + pad)} for w in windows),
        key=lambda w: w["start"],
    )
    merged: list[dict] = []
    for w in padded:
        if merged and w["start"] <= merged[-1]["end"]:
            last = merged[-1]
            last["end"] = max(last["end"], w["end"])
            last["reason"] = f"{last['reason']}; {w['reason']}"
        else:
            merged.append(dict(w))
    return merged


def subtract(windows: list[dict], searched: list[dict], *, min_len: float = 5.0) -> list[dict]:
    """The parts of `windows` not yet searched, dropping slivers under `min_len`
    seconds: too short to hold a visual worth a Gemini call."""
    out = []
    for w in windows:
        pieces = [(w["start"], w["end"])]
        for s in searched:
            pieces = [p for a, b in pieces
                      for p in ((a, min(b, s["start"])), (max(a, s["end"]), b)) if p[1] > p[0]]
        out += [w | {"start": a, "end": b} for a, b in pieces if b - a >= min_len]
    return out


def to_offset(seconds: float) -> str:
    """The API's offset format: decimal seconds with an 's' suffix."""
    return f"{seconds:g}s"


def resolve_times(item: dict, window: dict, *, tolerance: float = 2.0) -> tuple[float, float, str] | None:
    """Gemini's MM:SS for a match, as (start, end, basis) in video seconds.

    The prompt asks for times in the full video. Should Gemini count from the
    start of the clip instead, the times fall inside the clip's length, not
    inside the window, and are shifted. Anything else is rejected.
    """
    start, end = ts_seconds(item.get("start", "")), ts_seconds(item.get("end", ""))
    if start is None or end is None:
        return None
    end = max(end, start)
    if window["start"] - tolerance <= start <= window["end"] + tolerance:
        return start, end, "absolute"
    if start <= window["end"] - window["start"] + tolerance:
        return window["start"] + start, window["start"] + end, "relative"
    return None


def parse_windows_arg(value: str) -> list[dict]:
    windows = []
    for part in value.split(","):
        m = RANGE_RE.match(part)
        if not m:
            raise ValueError(f"not a time range: {part!r} (expected e.g. 3:20-4:20)")
        windows.append({
            "start": _ts_to_ms(m.group(1)) / 1000,
            "end": _ts_to_ms(m.group(2)) / 1000,
            "reason": "set by hand (--windows)",
        })
    return windows


def output_paths(repo: Path, slug: str, query: str) -> tuple[Path, Path]:
    from extract_stills import _slugify

    name = f"search-{_slugify(query, 50)}"
    return (repo / "raw" / "images" / slug / name,
            repo / "raw" / "videos" / f"{slug}.{name}.stills.md")


def render_search_manifest(*, slug: str, video_id: str, url: str, title: str, channel: str,
                           duration: float, query: str, stills_rel: str, windows: list[dict],
                           stills: list[dict], skipped: list[dict], extractor: dict,
                           usage: dict) -> str:
    import datetime as dt

    import yaml
    from fetch_transcript import _YtDumper

    mmss = lambda s: _format_duration(int(s))  # noqa: E731
    today = dt.date.today().isoformat()
    header = {
        "title": title,
        "video_id": video_id,
        "url": url,
        "channel": channel,
        "duration": _format_duration(int(duration)),
        "transcript": f"{slug}.md",
        "query": query,
        "stills_dir": stills_rel,
        "stills_count": len(stills),
        "windows": [f"{mmss(w['start'])}-{mmss(w['end'])} ({w['stage']})" for w in windows],
        "extractor": extractor,
        "acquired": today,
        "usage": usage,
        "notes": (
            "Targeted search (search_stills.py), not a full catalogue: only the windows\n"
            "above were sent to Gemini. Machine-read and unverified. At Process, view each\n"
            "PNG and correct the reading against the pixels before it reaches the wiki.\n"
        ),
    }
    out = [
        "---",
        yaml.dump(header, Dumper=_YtDumper, sort_keys=False, allow_unicode=True, width=100).rstrip(),
        "---",
        "",
        f"# Stills search: {title}",
        "",
        f"Query: **{query}**. Machine-read on {today}. **Unverified**: view each PNG and correct "
        "the reading before it reaches the wiki.",
        "",
        "## Windows searched",
        "",
    ]
    out += [f"- {mmss(w['start'])}–{mmss(w['end'])} · {w['stage']} · {w['reason']}" for w in windows]
    out.append("")
    for s in stills:
        out += [
            f"## {s['n']:02d} · [{mmss(s['at'])}] {s['title']}",
            "",
            f"- Kind: {s['kind']}",
            f"- On screen: {mmss(s['start_s'])}–{mmss(s['end_s'])} · still taken at {mmss(s['at'])}",
            f"- Found at stage: {s['stage']} (Gemini timestamps read as {s['time_basis']})",
            f"- File: `{stills_rel}{s['file']}`",
            f"- At this moment: https://www.youtube.com/watch?v={video_id}&t={int(s['at'])}s",
            "",
            f"Why it matches (machine-read): {s['match'].strip()}",
            "",
            "On-screen content (machine-read):",
            "",
            "```text",
            s["content"].strip(),
            "```",
            "",
            f"Adds vs. narration (machine-read): {s['adds'].strip()}",
            "",
        ]
    if skipped:
        out += ["## Skipped", ""]
        out += [f"- [{x.get('start')}–{x.get('end')}] {x.get('title')}: {x['reason']}" for x in skipped]
        out.append("")
    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Locate: Gemini reads the transcript
# ---------------------------------------------------------------------------

LOCATE_PROMPT = """\
Below is the timestamped transcript of a video. Someone wants to find this
visual in the video:

    {query}

The visual itself is not in the transcript. Find the moments where the speaker
is most likely showing it: where they introduce, explain or point at that topic,
or say things like "as you can see" or "this chart". Match on meaning, not on
exact words; the labels on a slide are often never spoken.

A talk often comes back to its topic. Give each separate passage where the
topic is discussed its own window, including later passages that return to it,
rather than several windows on the same passage.

Return at most {max_windows} windows, most likely first. For each: start and end
in the transcript's own format (M:SS or H:MM:SS), each window at most
{max_len} seconds long, and a one-sentence reason that quotes or paraphrases
what is said there. Return an empty list if the topic is never discussed.

Transcript:
{transcript}
"""

LOCATE_SCHEMA = {
    "type": "object",
    "properties": {
        "windows": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "string"},
                    "end": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["start", "end", "reason"],
            },
        }
    },
    "required": ["windows"],
}


def _usage(interaction) -> dict:
    from extract_stills import USAGE_KEYS

    usage = interaction.model_dump(mode="json", exclude_none=True).get("usage") or {}
    return {k: usage[k] for k in USAGE_KEYS if k in usage}


def _add_usage(total: dict, more: dict) -> dict:
    return {k: total.get(k, 0) + more.get(k, 0) for k in set(total) | set(more)}


def locate_windows(client, *, model: str, query: str, segments: list[tuple[float, str]],
                   max_windows: int, max_len: int) -> tuple[list[dict], dict]:
    prompt = LOCATE_PROMPT.format(query=query, max_windows=max_windows, max_len=max_len,
                                  transcript=transcript_for_prompt(segments))
    interaction = client.interactions.create(
        model=model,
        input=[{"type": "text", "text": prompt}],
        response_format={"type": "text", "mime_type": "application/json", "schema": LOCATE_SCHEMA},
    )
    windows = []
    for w in json.loads(interaction.output_text)["windows"][:max_windows]:
        start, end = ts_seconds(w.get("start", "")), ts_seconds(w.get("end", ""))
        if start is not None and end is not None:
            windows.append({"start": start, "end": max(end, start), "reason": w["reason"].strip()})
    return windows, _usage(interaction)


# ---------------------------------------------------------------------------
# Find: one Gemini video call per window
# ---------------------------------------------------------------------------

FIND_PROMPT = """\
This is the part of a longer video from {start} to {end}. Someone is looking for:

    {query}

List each information-bearing visual in this part that matches the request or
could plausibly answer it: slides, diagrams, charts, tables, code, whiteboard
drawings, on-screen text. Ignore talking-head shots and visuals unrelated to the
request. If a matching visual builds up, report each distinct state as its own item.

For each item:
- start, end: when it is on screen, as positions in the FULL video (M:SS or
  H:MM:SS), so between {start} and {end}. `end` is the last second it is
  visible in that state.
- kind: one of slide, diagram, chart, table, code, screen, whiteboard, text-overlay.
- title: the visual's own title if it has one, else a short descriptive title.
- content: all on-screen text verbatim, one element per line; table rows as
  `cell | cell`; arrows and relations as `A -> B`; axes and their labels for charts.
- adds: one sentence on what the visual conveys that the narration does not.
- match: one sentence on how it relates to the request.

Return an empty list if nothing in this part matches.
"""


def _find_schema() -> dict:
    from extract_stills import SCHEMA

    schema = json.loads(json.dumps(SCHEMA))
    item = schema["properties"]["visuals"]["items"]
    item["properties"]["match"] = {"type": "string"}
    item["required"].append("match")
    return schema


def find_in_window(client, *, model: str, url: str, query: str, window: dict | None,
                   fps: float, duration: float) -> tuple[list[dict], dict]:
    """Matches in one window (or, with window=None, in the whole video)."""
    processing: dict = {"type": "static", "fps": fps}
    span = window or {"start": 0.0, "end": duration}
    if window:
        processing |= {"start_offset": to_offset(window["start"]), "end_offset": to_offset(window["end"])}
    prompt = FIND_PROMPT.format(query=query, start=_format_duration(int(span["start"])),
                                end=_format_duration(int(span["end"])))
    interaction = client.interactions.create(
        model=model,
        input=[{"type": "video", "uri": url, "processing": processing}, {"type": "text", "text": prompt}],
        response_format={"type": "text", "mime_type": "application/json", "schema": _find_schema()},
    )
    return json.loads(interaction.output_text)["visuals"], _usage(interaction)


def search(client, *, model: str, url: str, query: str, windows: list[dict], fps: float,
           duration: float, widen: float, fallback: bool) -> tuple[list[dict], list[dict], dict]:
    """Run the stages until one finds a match. Returns (matches, windows searched, usage)."""
    usage: dict = {}
    searched: list[dict] = []
    matches: list[dict] = []

    def run(stage_windows: list[dict], stage: str) -> None:
        nonlocal usage
        for w in stage_windows:
            w = w | {"stage": stage}
            found, u = find_in_window(client, model=model, url=url, query=query,
                                      window=w, fps=fps, duration=duration)
            usage = _add_usage(usage, u)
            searched.append(w)
            matches.extend(m | {"_window": w, "stage": stage} for m in found)
            print(f"  {stage}: {_format_duration(int(w['start']))}-{_format_duration(int(w['end']))}"
                  f" -> {len(found)} match(es), {u.get('total_tokens', '?')} tokens", file=sys.stderr)

    run(windows, windows[0]["stage"] if windows else "located")
    if not matches and fallback:
        wider = subtract(pad_and_merge(windows, pad=widen, duration=duration), searched)
        run(wider, "widened")
    if not matches and fallback:
        print("  nothing in the windows; searching the whole video", file=sys.stderr)
        found, u = find_in_window(client, model=model, url=url, query=query,
                                  window=None, fps=1.0, duration=duration)
        usage = _add_usage(usage, u)
        whole = {"start": 0.0, "end": duration, "reason": "fallback: whole video", "stage": "whole-video"}
        searched.append(whole)
        matches.extend(m | {"_window": whole, "stage": "whole-video"} for m in found)
    return matches, searched, usage


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    from extract_stills import (DEFAULT_MODEL, DUPLICATE_MAD, FRAME_LEAD_S, REPO, STILL_RE,
                                _export_credential, _mad, _slugify, _thumbnail, open_frames)
    from fetch_transcript import extract_video_id

    ap = argparse.ArgumentParser(description="Find the stills that answer one question about a YouTube video.")
    ap.add_argument("url", help="YouTube URL or 11-char video ID")
    ap.add_argument("--slug", required=True, help="Raw slug, same as raw/videos/<slug>.md")
    ap.add_argument("--query", required=True, help='What to find, e.g. "the diagram explaining X"')
    ap.add_argument("--windows", help="Skip Locate and search these ranges, e.g. 3:20-4:20,12:00-13:00")
    ap.add_argument("--transcript", type=Path, help="Transcript to locate from (default: raw/videos/<slug>.md)")
    ap.add_argument("--max-windows", type=int, default=3, help="Windows Locate may propose (default: 3)")
    ap.add_argument("--max-len", type=int, default=90, help="Longest window Locate may propose, s (default: 90)")
    ap.add_argument("--pad", type=float, default=30, help="Seconds added each side of a window (default: 30)")
    ap.add_argument("--widen", type=float, default=120,
                    help="Padding for the widened fallback stage, s (default: 120)")
    ap.add_argument("--fps", type=float, default=2.0, help="Frame sampling inside windows (default: 2)")
    ap.add_argument("--no-fallback", action="store_true",
                    help="Stop after the first stage, even when it finds nothing")
    ap.add_argument("--locate-only", action="store_true", help="Print the windows and stop (no video calls)")
    ap.add_argument("--dry-run", action="store_true", help="Call Gemini, print matches as JSON, write nothing")
    ap.add_argument("--model", default=DEFAULT_MODEL, help=f"Gemini model (default: {DEFAULT_MODEL})")
    ap.add_argument("--repo", type=Path, default=REPO, help="Wiki repo root (default: this repo)")
    args = ap.parse_args()

    try:
        video_id = extract_video_id(args.url)
        manual = parse_windows_arg(args.windows) if args.windows else None
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    url = f"https://www.youtube.com/watch?v={video_id}"
    transcript = args.transcript or args.repo / "raw" / "videos" / f"{args.slug}.md"
    if not transcript.exists():
        print(f"error: no transcript at {transcript}. Fetch it first:\n"
              f"  python fetch_transcript.py {url} -o {transcript}", file=sys.stderr)
        return 2
    header, segments = parse_transcript(transcript.read_text(encoding="utf-8"))
    duration = float(header.get("length_seconds") or (segments[-1][0] + 60 if segments else 0))

    _export_credential()
    from google import genai

    client = genai.Client()  # bound to a name: a temporary is collected mid-call
    usage: dict = {}
    if manual:
        raw_windows, stage = manual, "manual"
    else:
        raw_windows, usage = locate_windows(client, model=args.model, query=args.query, segments=segments,
                                            max_windows=args.max_windows, max_len=args.max_len)
        stage = "located"
    windows = [w | {"stage": stage} for w in pad_and_merge(raw_windows, pad=args.pad, duration=duration)]
    print(f"Locate: {len(windows)} window(s), {usage.get('total_tokens', 0)} tokens", file=sys.stderr)
    for w in windows:
        print(f"  {_format_duration(int(w['start']))}-{_format_duration(int(w['end']))}  {w['reason']}",
              file=sys.stderr)
    if args.locate_only:
        json.dump({"windows": windows, "usage": usage}, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0 if windows else 1

    matches, searched, find_usage = search(
        client, model=args.model, url=url, query=args.query, windows=windows, fps=args.fps,
        duration=duration, widen=args.widen, fallback=not args.no_fallback)
    usage = _add_usage(usage, find_usage)
    if args.dry_run:
        json.dump({"windows": searched, "matches": matches, "usage": usage}, sys.stdout,
                  ensure_ascii=False, indent=2, default=str)
        sys.stdout.write("\n")
        return 0 if matches else 1

    stills_dir, manifest = output_paths(args.repo, args.slug, args.query)
    stills_dir.mkdir(parents=True, exist_ok=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    # Re-running the same query replaces its own stills, never the full-scan set.
    for old in stills_dir.iterdir():
        if STILL_RE.match(old.name):
            old.unlink()

    stills: list[dict] = []
    skipped: list[dict] = []
    thumbs: list[bytes] = []
    with tempfile.TemporaryDirectory() as tmp:
        frames, info = open_frames(url, Path(tmp))
        for item in matches:
            resolved = resolve_times(item, item["_window"])
            if resolved is None:
                skipped.append(item | {"reason": "timestamps unparseable or outside the window"})
                continue
            start, end, basis = resolved
            end = min(end, duration - 0.5)
            at = max(start, end - FRAME_LEAD_S)
            n = len(stills) + 1
            name = f"{n:02d}-{int(at) // 60:02d}m{int(at) % 60:02d}-{_slugify(item['title'])}.png"
            frames.grab(at, stills_dir / name)
            thumb = _thumbnail(stills_dir / name)
            twin = next((s for s, t in zip(stills, thumbs) if _mad(t, thumb) < DUPLICATE_MAD), None)
            if twin:
                (stills_dir / name).unlink()
                skipped.append(item | {"reason": f"same picture as still {twin['n']:02d}"})
                continue
            thumbs.append(thumb)
            stills.append(item | {"n": n, "start_s": start, "end_s": end, "at": at, "file": name,
                                  "time_basis": basis})

    rel = f"../images/{args.slug}/{stills_dir.name}/"
    manifest.write_text(
        render_search_manifest(
            slug=args.slug, video_id=video_id, url=url, title=info.get("title") or header.get("title"),
            channel=info.get("channel") or header.get("channel"), duration=duration, query=args.query,
            stills_rel=rel, windows=searched, stills=stills, skipped=skipped,
            extractor={"model": args.model, "processing": "static, windowed", "fps": args.fps,
                       "pad_s": args.pad, "frame_rule": f"end of display window minus {FRAME_LEAD_S:g}s",
                       "frames": frames.summary()},
            usage=usage),
        encoding="utf-8",
    )
    print(f"wrote {len(stills)} stills to {stills_dir} and {manifest} "
          f"({len(skipped)} skipped; {usage.get('total_tokens', '?')} Gemini tokens; {frames.summary()})")
    return 0 if stills else 1


if __name__ == "__main__":
    sys.exit(main())
