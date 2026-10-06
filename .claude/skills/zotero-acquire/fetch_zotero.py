#!/usr/bin/env python3
"""zotero-acquire — pull items from a local Zotero collection into raw/<type>/ stubs.

Acquire-phase tool for the LLM wiki (see CLAUDE.md §Ingest / §Acquire). Reads the
local Zotero 7 HTTP API via pyzotero (no cloud account, no API key), and for each
top-level item in a chosen collection:

  1. copies the item's primary binary attachment (PDF/DOCX/EPUB) into the matching
     raw/<type>/ folder — gitignored, co-located by type;
  2. converts it to markdown with the repo's normal pipeline
     (marker -> markitdown -> pdftotext, whichever is installed);
  3. writes a markdown stub carrying the Acquire->Process frontmatter contract.

It NEVER touches wiki/. The human-supervised Process step turns each stub into a
wiki/sources/ page.

Usage:
    python fetch_zotero.py --collection ev-wiki
    python fetch_zotero.py --collection "State of AI" --dry-run
    python fetch_zotero.py -c ev-wiki --limit 3 --json

Requires the Zotero desktop app running with its local API enabled
(Settings -> Advanced -> "Allow other applications on this computer to
communicate with Zotero").
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML required: pip install pyyaml  (or run via uv with requirements.txt)")
try:
    from pyzotero import zotero
except ImportError:
    sys.exit("pyzotero required: pip install pyzotero  (or run via uv with requirements.txt)")


# Zotero itemType -> raw/<type>/ folder. A first guess only; Process corrects it
# (e.g. a report typed `webpage` in Zotero). Edit freely.
ITEM_TYPE_MAP = {
    "journalArticle": "papers",
    "conferencePaper": "papers",
    "preprint": "papers",
    "thesis": "papers",
    "report": "reports",
    "book": "books",
    "bookSection": "books",
    "magazineArticle": "articles",
    "newspaperArticle": "articles",
    "blogPost": "articles",
    "webpage": "articles",
    "document": "articles",
    "presentation": "lectures",
    "videoRecording": "videos",
    "podcast": "videos",
}
DEFAULT_TYPE = "articles"

# Attachment contentType -> short kind, in preference order (PDF first).
CONVERTIBLE_CT = [
    ("application/pdf", "pdf"),
    ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
    ("application/epub+zip", "epub"),
    ("text/html", "html"),
]
# Only these extensions get copied into raw/ (they are gitignored binaries).
# Text formats (html) are converted from the Zotero source path without copying,
# so we never commit a scraped page into the repo.
BINARY_EXT = {"pdf", "docx", "epub", "mobi"}

# Video-URL detection. A videoRecording (or any item) whose URL is a YouTube
# watch/short/youtu.be link is auto-delegated to the youtube-transcript-skill so
# the raw file carries the real transcript, not just Zotero's abstract. Vimeo is
# detected too, but youtube-transcript-skill is YouTube-only — Vimeo falls back
# to the Zotero stub with a note (no transcript channel exists yet).
YOUTUBE_RE = re.compile(r"(?:youtube\.com/(?:watch\?v=|shorts/|live/)|youtu\.be/)", re.I)
VIMEO_RE = re.compile(r"vimeo\.com/\d+", re.I)


def is_youtube(url: str) -> bool:
    return bool(url and YOUTUBE_RE.search(url))


def is_vimeo(url: str) -> bool:
    return bool(url and VIMEO_RE.search(url))


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def slugify(text: str, maxlen: int = 80) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:maxlen].rstrip("-") or "untitled"


def repo_root() -> Path:
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / "CLAUDE.md").exists() and (parent / "raw").exists():
            return parent
    return p.parents[3]


def creators_to_authors(creators) -> list[str]:
    out = []
    for c in creators or []:
        if c.get("name"):
            out.append(c["name"])
        else:
            nm = " ".join(x for x in (c.get("firstName"), c.get("lastName")) if x).strip()
            if nm:
                out.append(nm)
    return out


def norm_date(raw: str) -> str:
    """Best-effort ISO date from Zotero's freeform `date` field."""
    if not raw:
        return ""
    m = re.search(r"(\d{4})(?:[-/](\d{1,2}))?(?:[-/](\d{1,2}))?", raw)
    if not m:
        return raw.strip()
    y, mo, d = m.group(1), m.group(2), m.group(3)
    if mo and d:
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    if mo:
        return f"{y}-{int(mo):02d}"
    return y


def extract_citekey(data: dict) -> str:
    """Better BibTeX writes 'Citation Key: xyz' into the Zotero `extra` field."""
    m = re.search(r"(?:Citation Key|citekey)\s*:\s*(\S+)", data.get("extra", "") or "", re.I)
    return m.group(1) if m else ""


# --------------------------------------------------------------------------- #
# converters (priority order; each returns markdown text or None)
# --------------------------------------------------------------------------- #
def _conv_marker(src: Path):
    if not shutil.which("marker_single"):
        return None
    with tempfile.TemporaryDirectory() as td:
        r = subprocess.run(
            ["marker_single", str(src), "--output_dir", td],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            return None
        mds = sorted(Path(td).rglob("*.md"))
        if mds:
            return mds[0].read_text(encoding="utf-8", errors="replace")
    return None


def _conv_markitdown(src: Path):
    if not shutil.which("markitdown"):
        return None
    r = subprocess.run(["markitdown", str(src)], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 and r.stdout.strip() else None


def _conv_pdftotext(src: Path):
    if src.suffix.lower() != ".pdf" or not shutil.which("pdftotext"):
        return None
    r = subprocess.run(["pdftotext", "-layout", str(src), "-"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 and r.stdout.strip() else None


CONVERTERS = [
    ("marker", _conv_marker),
    ("markitdown", _conv_markitdown),
    ("pdftotext", _conv_pdftotext),
]


def convert(src: Path):
    """Return (markdown_text, converter_name) or (None, None)."""
    for name, fn in CONVERTERS:
        try:
            out = fn(src)
        except Exception:
            out = None
        if out:
            return out, name
    return None, None


# --------------------------------------------------------------------------- #
# YouTube delegation (youtube-transcript-skill)
# --------------------------------------------------------------------------- #
def youtube_skill_dir() -> Path | None:
    """Locate the sibling youtube-transcript-skill directory."""
    d = Path(__file__).resolve().parent.parent / "youtube-transcript-skill"
    return d if (d / "fetch_transcript.py").exists() else None


def fetch_transcript_json(url: str, yt_dir: Path, timeout_ms: int = 30000, retries: int = 1):
    """Run youtube-transcript-skill via uv and return its parsed JSON.

    The skill is flaky (the transcript panel intermittently fails to render); on an
    empty result we retry once with a longer per-step timeout. Playwright browser
    binaries live in a global cache, so `uv run` with the skill's requirements finds
    the already-installed Chromium. Returns the parsed dict (possibly transcript-less)
    or None if it could not be run/parsed at all.
    """
    req, script = yt_dir / "requirements.txt", yt_dir / "fetch_transcript.py"
    last, tmo = None, timeout_ms
    for _ in range(retries + 1):
        cmd = ["uv", "run", "--with-requirements", str(req), "python", str(script),
               url, "--json", "--timeout", str(tmo)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=tmo / 1000 + 240)
        except Exception:
            tmo = max(tmo * 2, 60000)
            continue
        try:
            last = json.loads(r.stdout)
        except Exception:
            last = None
        if last and last.get("transcript"):
            return last
        tmo = max(tmo * 2, 60000)  # flaky-panel retry with a longer timeout
    return last


def build_video_markdown(meta: dict, segs: list, zkey: str, collection: str) -> str:
    """Build a raw video file: Zotero provenance + video metadata + chaptered transcript.

    Mirrors the youtube-transcript-skill markdown contract, with the two Zotero
    provenance fields prepended so dedup-on-`zotero_item_key` and re-location still work.
    Chapters are bucketed by their `start` LABEL (Zotero/skill `start_ms` is unreliable).
    """
    def to_sec(ts: str) -> int:
        p = [int(x) for x in ts.split(":")]
        return p[0] * 3600 + p[1] * 60 + p[2] if len(p) == 3 else p[0] * 60 + p[1]

    fm = {"zotero_item_key": zkey, "zotero_collection": collection}
    for k, v in meta.items():
        if v not in (None, "", []):
            fm[k] = v
    head = yaml.dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False, width=100).rstrip()
    out = ["---", head, "---", ""]

    chapters = sorted((meta.get("chapters") or []), key=lambda c: to_sec(c.get("start", "0:00")))
    if chapters:
        cstarts = [to_sec(c.get("start", "0:00")) for c in chapters]
        ci = 0
        out += [f"## [{chapters[0].get('start')}] {chapters[0].get('title', '')}", ""]
        for s in segs:
            sec = to_sec(s["ts"])
            while ci + 1 < len(chapters) and sec >= cstarts[ci + 1]:
                ci += 1
                out += ["", f"## [{chapters[ci].get('start')}] {chapters[ci].get('title', '')}", ""]
            out.append(f"[{s['ts']}] {s['text'].strip()}")
    else:
        out += ["## Transcript", ""] + [f"[{s['ts']}] {s['text'].strip()}" for s in segs]
    return "\n".join(out).rstrip() + "\n"


# --------------------------------------------------------------------------- #
# Zotero access
# --------------------------------------------------------------------------- #
def pick_attachment(children):
    """Return (attachment_item, kind) preferring PDF, then docx/epub/html, then any file."""
    atts = [c for c in children if c["data"].get("itemType") == "attachment"]
    for ct, kind in CONVERTIBLE_CT:
        for c in atts:
            if c["data"].get("contentType") == ct:
                return c, kind
    for c in atts:
        if c["data"].get("filename"):
            return c, None
    return None, None


def attachment_path(data_dir: Path, att) -> Path | None:
    data = att["data"]
    if data.get("linkMode") == "linked_file" and data.get("path"):
        return Path(data["path"]).expanduser()
    fn = data.get("filename")
    if not fn:
        return None
    return data_dir / "storage" / att["key"] / fn


def zotero_fulltext(zot, attachment_key: str):
    try:
        content = (zot.fulltext_item(attachment_key) or {}).get("content", "")
        if content.strip():
            return content, "zotero-extracted"
    except Exception:
        pass
    return "", "none"


def existing_keys(raw_dir: Path) -> set[str]:
    keys: set[str] = set()
    for md in raw_dir.rglob("*.md"):
        try:
            head = md.read_text(encoding="utf-8", errors="replace")[:2000]
        except Exception:
            continue
        m = re.search(r"^zotero_item_key:\s*(\S+)", head, re.MULTILINE)
        if m:
            keys.add(m.group(1).strip().strip("\"'"))
    return keys


# --------------------------------------------------------------------------- #
# per-item processing
# --------------------------------------------------------------------------- #
def build_stub(meta: dict, body: str) -> str:
    fm = yaml.dump(
        meta, sort_keys=False, allow_unicode=True, default_flow_style=False, width=100
    ).rstrip()
    return f"---\n{fm}\n---\n\n{body.rstrip()}\n"


def process_item(zot, item, collection, data_dir, raw_dir, seen, force, dry_run,
                 video_delegate=True, yt_dir=None, yt_timeout=30000) -> dict:
    data = item["data"]
    key = item["key"]
    itype = data.get("itemType", "")
    title = data.get("title") or "(untitled)"
    slug = slugify(title)
    folder = ITEM_TYPE_MAP.get(itype, DEFAULT_TYPE)
    url = data.get("url", "")

    if key in seen and not force:
        return {"key": key, "type": itype, "slug": slug, "action": "skip (already acquired)"}

    # --- YouTube/Vimeo delegation -----------------------------------------
    # A video URL means the real content is a transcript Zotero does not hold.
    # YouTube -> delegate to youtube-transcript-skill and write a videos/ file with
    # the transcript + Zotero provenance. Vimeo is detected but unsupported by the
    # skill, so it falls through to the Zotero stub with a note.
    delegate_note = ""
    if video_delegate and is_youtube(url):
        if dry_run:
            seen.add(key)
            return {"key": key, "type": itype, "slug": slugify(title),
                    "action": "would delegate to youtube-transcript-skill -> videos/<title>.md",
                    "attachment": "-", "converter": "youtube-transcript", "fulltext": "transcript"}
        yt = fetch_transcript_json(url, yt_dir, yt_timeout) if yt_dir else None
        if yt and yt.get("transcript"):
            ymeta = yt.get("metadata") or {}
            vslug = slugify(ymeta.get("title") or title)
            target = raw_dir / "videos" / f"{vslug}.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(build_video_markdown(ymeta, yt["transcript"], key, collection),
                              encoding="utf-8")
            seen.add(key)
            return {"key": key, "type": itype, "slug": vslug,
                    "action": f"wrote videos/{vslug}.md (youtube-transcript)",
                    "attachment": "-", "converter": "youtube-transcript", "fulltext": "transcript"}
        delegate_note = (" YouTube URL detected but youtube-transcript-skill returned no transcript "
                         "(flaky panel / no captions) — wrote a stub from Zotero metadata; re-run the "
                         "skill manually to attach the transcript.")
    elif video_delegate and is_vimeo(url):
        delegate_note = (" Vimeo URL detected, but youtube-transcript-skill is YouTube-only — wrote a "
                         "stub from Zotero metadata; fetch the Vimeo transcript by hand.")

    attachment_name, converter, body = "", "", ""
    fulltext_source = "none"

    att, _kind = pick_attachment(zot.children(key))
    if att:
        src = attachment_path(data_dir, att)
        if src and src.exists():
            ext = src.suffix.lower().lstrip(".")
            if ext in BINARY_EXT:
                dest = raw_dir / folder / f"{slug}.{ext}"
                if not dry_run:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)
                attachment_name = dest.name
            md, converter = convert(src)
            if md:
                body = md
                fulltext_source = "pdf-converted" if ext == "pdf" else "doc-converted"
            else:
                body, fulltext_source = zotero_fulltext(zot, att["key"])
        else:
            body, fulltext_source = zotero_fulltext(zot, att["key"])

    if not body:
        body = data.get("abstractNote") or "_(no extractable full text — see source URL)_"

    meta = {
        "zotero_item_key": key,
        "zotero_collection": collection,
        "item_type": itype,
        "title": title,
        "authors": creators_to_authors(data.get("creators")),
        "date_published": norm_date(data.get("date")),
        "doi": data.get("DOI", ""),
        "isbn": data.get("ISBN", ""),
        "url": data.get("url", ""),
        "citekey": extract_citekey(data),
        "abstract": data.get("abstractNote", ""),
    }
    if attachment_name:
        meta["attachment"] = attachment_name
    meta["fulltext_source"] = fulltext_source
    meta["converter"] = converter or ""
    meta["notes"] = (
        f"Acquired from Zotero collection `{collection}`. "
        f"itemType `{itype}` routed to raw/{folder}/ — confirm routing + identity at Process."
        + delegate_note
    )

    target = raw_dir / folder / f"{slug}.md"
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(build_stub(meta, body), encoding="utf-8")
    seen.add(key)

    verb = "would write" if dry_run else "wrote"
    return {
        "key": key, "type": itype, "slug": slug,
        "action": f"{verb} {folder}/{slug}.md",
        "attachment": attachment_name or "-",
        "converter": converter or "-",
        "fulltext": fulltext_source,
    }


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="Acquire a local Zotero collection into raw/ stubs.")
    ap.add_argument("-c", "--collection", default="ev-wiki", help="Zotero collection name (default: ev-wiki)")
    ap.add_argument("--data-dir", default=str(Path.home() / "Zotero"), help="Zotero data dir (default: ~/Zotero)")
    ap.add_argument("--raw-dir", default=None, help="raw/ dir (default: repo raw/)")
    ap.add_argument("--limit", type=int, default=0, help="Max items to process (0 = all)")
    ap.add_argument("--dry-run", action="store_true", help="Plan only; write/copy nothing")
    ap.add_argument("--force", action="store_true", help="Re-acquire even if zotero_item_key already present")
    ap.add_argument("--json", action="store_true", help="Emit per-item results as JSON to stdout")
    ap.add_argument("--no-video-delegate", action="store_true",
                    help="Disable auto-delegation of YouTube URLs to youtube-transcript-skill")
    ap.add_argument("--yt-timeout", type=int, default=30000,
                    help="Per-step timeout (ms) for the youtube-transcript-skill (default: 30000)")
    args = ap.parse_args()

    data_dir = Path(args.data_dir).expanduser()
    raw_dir = Path(args.raw_dir).expanduser() if args.raw_dir else repo_root() / "raw"

    video_delegate = not args.no_video_delegate
    yt_dir = youtube_skill_dir()
    if video_delegate and yt_dir is None:
        print("warning: youtube-transcript-skill not found alongside this skill — "
              "YouTube items will fall back to Zotero stubs.", file=sys.stderr)

    zot = zotero.Zotero(0, "user", local=True)
    cols = zot.collections()
    target = args.collection.strip().lower()
    key = next((c["key"] for c in cols if c["data"]["name"].strip().lower() == target), None)
    if not key:
        names = ", ".join(sorted(c["data"]["name"] for c in cols))
        sys.exit(f"collection not found: {args.collection!r}\navailable: {names}")

    items = [it for it in zot.everything(zot.collection_items_top(key))
             if it["data"].get("itemType") not in ("attachment", "note")]
    if args.limit:
        items = items[: args.limit]

    seen = existing_keys(raw_dir)
    results = [process_item(zot, it, args.collection, data_dir, raw_dir, seen, args.force, args.dry_run,
                            video_delegate=video_delegate, yt_dir=yt_dir, yt_timeout=args.yt_timeout)
               for it in items]

    if args.json:
        json.dump(results, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        mode = "DRY RUN" if args.dry_run else "ACQUIRE"
        print(f"[{mode}] collection {args.collection!r} ({key}) — {len(items)} item(s); raw -> {raw_dir}")
        for r in results:
            extra = "" if r["action"].startswith("skip") else \
                f"  [type={r.get('type','')} att={r.get('attachment','-')} conv={r.get('converter','-')} ft={r.get('fulltext','-')}]"
            print(f"  - {r['action']}{extra}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
