#!/usr/bin/env python3
"""
Save stills of the information-bearing visuals in a YouTube video — slides,
diagrams, charts, tables, code — plus a machine-read manifest of what each one
shows.

Gemini finds the visuals and reads them. It returns text only (timestamps and
on-screen content), never images, so the stills are cut locally: yt-dlp
resolves the stream URL and ffmpeg seeks it for one frame per visual. The video
is downloaded only if a seek fails (FrameSource).

Acquire-phase only. Writes:
    raw/images/<slug>/NN-MMmSS-<title>.png   (gitignored)
    raw/videos/<slug>.stills.md              (manifest, committed)

Usage:
    python extract_stills.py "https://www.youtube.com/watch?v=VIDEO_ID" --slug <slug>
    python extract_stills.py URL --slug <slug> --dry-run > findings.json
    python extract_stills.py URL --slug <slug> --findings findings.json
    python extract_stills.py URL --slug <slug> --mode agentic
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

from fetch_transcript import _YtDumper, _format_duration, extract_video_id, ts_seconds


REPO = Path(__file__).resolve().parents[3]
DEFAULT_MODEL = "gemini-3.8-flash"

# One frame this far before the end of the display window. Slides that build up
# only gain content over time, so the last stable frame carries the most; the
# lead keeps us clear of the cut to whatever comes next.
FRAME_LEAD_S = 1.0

# Mean absolute difference (0-255) between 160x90 grayscale thumbnails below
# which two stills count as the same picture. Calibrated on the Fung talk
# (igO8iyca2_g): a slide shown twice scored <= 0.24, two different slides on the
# same template >= 3.50. At 16x16 with a 3.0 cut-off, text differences vanished
# and four distinct slides were dropped as repeats. Erring high keeps a
# duplicate, which Process discards; erring low loses a slide.
THUMB_SIZE = "160:90"
DUPLICATE_MAD = 1.0

STILL_RE = re.compile(r"^\d{2}-\d+m\d{2}-.*\.png$")

KINDS = ["slide", "diagram", "chart", "table", "code", "screen", "whiteboard", "text-overlay"]

PROMPT = """\
Catalogue the information-bearing visuals in this video, so that a still of each
can be saved to a knowledge base.

Include: slides, diagrams, charts, tables, code, screen recordings that show
specific content, whiteboard drawings, and on-screen text that carries a
substantive claim.
Exclude: talking-head shots, title cards, intro and outro bumpers, logos,
decorative B-roll, subscribe prompts.

If a visual builds up or changes substantively (new labels, a new highlight, a
different diagram), report each distinct state as its own item.

For each item:
- start, end: when it is on screen, as MM:SS (H:MM:SS past one hour). `end` is
  the last second it is visible in that state.
- kind: one of slide, diagram, chart, table, code, screen, whiteboard, text-overlay.
- title: the visual's own title if it has one, else a short descriptive title.
- content: all on-screen text verbatim, one element per line; table rows as
  `cell | cell`; arrows and relations as `A -> B`.
- adds: one sentence on what the visual conveys that the narration does not,
  or "nothing beyond the narration".

Return the items in chronological order.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "visuals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "string"},
                    "end": {"type": "string"},
                    "kind": {"type": "string", "enum": KINDS},
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                    "adds": {"type": "string"},
                },
                "required": ["start", "end", "kind", "title", "content", "adds"],
            },
        }
    },
    "required": ["visuals"],
}

USAGE_KEYS = [
    "total_tokens",
    "total_input_tokens",
    "total_cached_tokens",
    "total_output_tokens",
    "total_thought_tokens",
    "total_tool_use_tokens",
]


# ---------------------------------------------------------------------------
# Find: Gemini
# ---------------------------------------------------------------------------

def _export_credential() -> None:
    """genai.Client() reads GEMINI_API_KEY from the environment. The repo's
    .env spells it GEMINI-API-KEY, which a shell cannot `source`."""
    if os.environ.get("GEMINI_API_KEY"):
        return
    env_file = REPO / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            name, sep, value = line.partition("=")
            if sep and name.strip() in ("GEMINI_API_KEY", "GEMINI-API-KEY"):
                os.environ["GEMINI_API_KEY"] = value.strip().strip("\"'")
                return
    raise SystemExit("error: no Gemini credential (set GEMINI_API_KEY or add it to .env)")


def find_visuals(url: str, *, model: str, mode: str, resolution: str | None,
                 fps: float | None) -> dict:
    from google import genai

    _export_credential()
    processing: str | dict = mode
    if mode == "static" and fps:
        processing = {"type": "static", "fps": fps}
    video = {"type": "video", "uri": url, "processing": processing}
    if resolution:
        video["resolution"] = resolution

    # Keep the client bound: a temporary is collected mid-call and its
    # destructor closes the HTTP connection before the request goes out.
    client = genai.Client()
    interaction = client.interactions.create(
        model=model,
        input=[video, {"type": "text", "text": PROMPT}],
        response_format={"type": "text", "mime_type": "application/json", "schema": SCHEMA},
    )
    dumped = interaction.model_dump(mode="json", exclude_none=True)
    usage = dumped.get("usage") or {}
    steps = dumped.get("steps") or []
    return {
        "visuals": json.loads(interaction.output_text)["visuals"],
        "extractor": {
            "model": model,
            "processing": mode,
            "resolution": resolution or "default",
            "fps": fps if mode == "static" else None,
            "processing_rounds": sum(1 for s in steps if s.get("type") == "processing_call"),
        },
        "usage": {k: usage[k] for k in USAGE_KEYS if k in usage},
    }


# ---------------------------------------------------------------------------
# Grab: yt-dlp + ffmpeg
# ---------------------------------------------------------------------------

# avc1 first: it decodes everywhere; AV1/VP9 only as a fallback.
VIDEO_FORMAT = "bv*[height<=1080][vcodec^=avc1]/bv*[height<=1080]/b[height<=1080]/b"


def download(url: str, dest: Path) -> tuple[Path, dict]:
    import yt_dlp

    opts = {
        "format": VIDEO_FORMAT,
        "outtmpl": str(dest / "video.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return Path(ydl.prepare_filename(info)), info


def grab_frame(video: Path | str, at_s: float, out: Path) -> None:
    """One frame at at_s. `video` is a local file or a stream URL: with -ss
    before -i, ffmpeg seeks a URL by HTTP range requests, reading only the
    bytes around the nearest keyframe."""
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{at_s:.2f}", "-i", str(video),
         "-frames:v", "1", "-update", "1", str(out)],
        check=True,
    )


class FrameSource:
    """Grabs frames by seeking the stream; downloads the video only as a fallback.

    The first failed seek triggers one full download, and every later frame
    comes from that local copy. On an 8-hour stream (2026-10-03) the old
    always-download path pulled 3.4 GB per run to cut a few dozen frames.
    """

    def __init__(self, stream_url: str | None, download, grab=grab_frame):
        self.stream_url = stream_url
        self._download = download  # () -> Path, called at most once
        self._grab = grab
        self.local: Path | None = None
        self.seeks = 0
        self.local_grabs = 0

    def grab(self, at_s: float, out: Path) -> None:
        if self.local is None and self.stream_url:
            try:
                self._grab(self.stream_url, at_s, out)
                self.seeks += 1
                return
            except (subprocess.CalledProcessError, OSError):
                pass  # fall through to the downloaded copy
        if self.local is None:
            self.local = self._download()
        self._grab(self.local, at_s, out)
        self.local_grabs += 1

    def summary(self) -> str:
        if self.local is None:
            return f"{self.seeks} frames by stream seek, no download"
        return f"{self.seeks} frames by stream seek, {self.local_grabs} from a full download (fallback)"


def open_frames(url: str, dest: Path) -> tuple[FrameSource, dict]:
    """A FrameSource for `url` and its metadata, without downloading the video."""
    import yt_dlp

    opts = {"format": VIDEO_FORMAT, "quiet": True, "no_warnings": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    # A single selected format carries its own URL; a merged pair does not.
    stream_url = info.get("url") if not info.get("requested_formats") else None
    return FrameSource(stream_url, lambda: download(url, dest)[0]), info


def _thumbnail(png: Path) -> bytes:
    return subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", str(png),
         "-vf", f"scale={THUMB_SIZE},format=gray", "-f", "rawvideo", "-"],
        check=True, capture_output=True,
    ).stdout


def _mad(a: bytes, b: bytes) -> float:
    return sum(abs(x - y) for x, y in zip(a, b)) / max(len(a), 1)


def _window(item: dict, duration: float) -> tuple[float, float] | None:
    """(start, end) in seconds, or None when Gemini's timestamps are unusable."""
    start, end = ts_seconds(item.get("start", "")), ts_seconds(item.get("end", ""))
    if start is None or end is None:
        return None
    end = max(end, start)
    if start >= duration:
        return None
    return start, min(end, duration - 0.5)


def _slugify(text: str, limit: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:limit].rstrip("-") or "still"


def _mmss(seconds: float) -> str:
    return _format_duration(int(seconds))


# ---------------------------------------------------------------------------
# Land: PNGs + manifest
# ---------------------------------------------------------------------------

def render_manifest(*, slug: str, video_id: str, url: str, info: dict, findings: dict,
                    stills: list[dict], skipped: list[dict], frames: str | None = None) -> str:
    today = dt.date.today().isoformat()
    model = findings["extractor"]["model"]
    header = {
        "title": info.get("title"),
        "video_id": video_id,
        "url": url,
        "channel": info.get("channel"),
        "duration": _format_duration(int(info.get("duration") or 0)),
        "transcript": f"{slug}.md",
        "stills_dir": f"../images/{slug}/",
        "stills_count": len(stills),
        "extractor": {k: v for k, v in findings["extractor"].items() if v is not None}
        | {"frame_rule": f"end of display window minus {FRAME_LEAD_S:g}s"}
        | ({"frames": frames} if frames else {}),
        "acquired": today,
        "usage": findings["usage"],
        "notes": (
            f"Machine-read by {model}; unverified. Stills are gitignored (raw/**/*.png).\n"
            "At Process, view each PNG, correct the reading against the pixels, and\n"
            "publish the selected stills as webp under wiki/assets/<source-page-slug>/.\n"
        ),
    }
    out = [
        "---",
        yaml.dump(header, Dumper=_YtDumper, sort_keys=False, allow_unicode=True, width=100).rstrip(),
        "---",
        "",
        f"# Stills: {info.get('title')}",
        "",
        f"Machine-read by `{model}` ({findings['extractor']['processing']} processing) on "
        f"{today}. **Unverified**: view each PNG and correct the reading before it reaches the wiki.",
        "",
    ]
    for s in stills:
        out += [
            f"## {s['n']:02d} · [{_mmss(s['at'])}] {s['title']}",
            "",
            f"- Kind: {s['kind']}",
            f"- On screen: {_mmss(s['start_s'])}–{_mmss(s['end_s'])} · still taken at {_mmss(s['at'])}",
            f"- File: `../images/{slug}/{s['file']}`",
            f"- At this moment: https://www.youtube.com/watch?v={video_id}&t={int(s['at'])}s",
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
        out += [f"- [{x['start']}–{x['end']}] {x['title']}: {x['reason']}" for x in skipped]
        out.append("")
    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Save stills of a YouTube video's slides and diagrams.")
    ap.add_argument("url", help="YouTube URL or 11-char video ID")
    ap.add_argument("--slug", required=True, help="Raw slug, same as raw/videos/<slug>.md")
    ap.add_argument("--mode", choices=["static", "agentic"], default="static",
                    help="Gemini video processing (default: static; agentic cost 33x more on a "
                         "3-minute video and failed on a 29-minute one, see SKILL.md)")
    ap.add_argument("--resolution", choices=["low", "medium", "high", "ultra_high"],
                    help="Gemini media resolution (default: the API's)")
    ap.add_argument("--fps", type=float, help="Frame sampling for static mode (default: the API's 1 fps)")
    ap.add_argument("--model", default=DEFAULT_MODEL, help=f"Gemini model (default: {DEFAULT_MODEL})")
    ap.add_argument("--findings", type=Path,
                    help="Reuse a saved --dry-run result instead of calling Gemini again")
    ap.add_argument("--dry-run", action="store_true",
                    help="Call Gemini, print findings as JSON, write nothing")
    ap.add_argument("--repo", type=Path, default=REPO, help="Wiki repo root (default: this repo)")
    args = ap.parse_args()

    try:
        video_id = extract_video_id(args.url)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    url = f"https://www.youtube.com/watch?v={video_id}"

    if args.findings:
        findings = json.loads(args.findings.read_text())
    else:
        findings = find_visuals(url, model=args.model, mode=args.mode,
                                resolution=args.resolution, fps=args.fps)
    if args.dry_run:
        json.dump(findings, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    stills_dir = args.repo / "raw" / "images" / args.slug
    manifest = args.repo / "raw" / "videos" / f"{args.slug}.stills.md"
    stills_dir.mkdir(parents=True, exist_ok=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    # Re-acquiring replaces the previous stills, per the Acquire contract.
    for old in stills_dir.iterdir():
        if STILL_RE.match(old.name):
            old.unlink()

    stills: list[dict] = []
    skipped: list[dict] = []
    thumbs: list[bytes] = []
    with tempfile.TemporaryDirectory() as tmp:
        frames, info = open_frames(url, Path(tmp))
        duration = float(info.get("duration") or 0)
        for item in findings["visuals"]:
            window = _window(item, duration)
            if window is None:
                skipped.append(item | {"reason": "timestamps unparseable or past the end"})
                continue
            start, end = window
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
            stills.append(item | {"n": n, "start_s": start, "end_s": end, "at": at, "file": name})

    manifest.write_text(
        render_manifest(slug=args.slug, video_id=video_id, url=url, info=info,
                        findings=findings, stills=stills, skipped=skipped,
                        frames=frames.summary()),
        encoding="utf-8",
    )
    tokens = findings["usage"].get("total_tokens", "?")
    print(f"wrote {len(stills)} stills to {stills_dir} and {manifest} "
          f"({len(skipped)} skipped; {tokens} Gemini tokens; {frames.summary()})")
    return 0 if stills else 1


if __name__ == "__main__":
    sys.exit(main())
