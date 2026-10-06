"""Offline tests for the WebVTT parser behind `fetch_transcript.py --sub-lang`.

Run from the repo root:
    python -m unittest discover -s .claude/skills/youtube-transcript-skill/tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fetch_transcript  # noqa: E402

# Shape of YouTube's automatic Dutch track, cut from an ANWB review
# (EFAu5nYWeCM, 0:06–0:17). Note the cue whose first text line is one space:
# a blank-line split cut "Goed voorbeeld…" off its timing line (2026-10-06).
ROLLING = """WEBVTT
Kind: captions
Language: nl

00:00:05.990 --> 00:00:08.270 align:start position:0%
gemoeten, hè? Of niet? Ik denk het wel. Ja,
maar<00:00:06.200><c> nou</c><00:00:06.399><c> komt</c><00:00:06.640><c> het.</c><00:00:07.640><c> 418</c>

00:00:08.270 --> 00:00:08.280 align:start position:0%
maar nou komt het. Hier zie je geen 418


00:00:08.280 --> 00:00:13.470 align:start position:0%
maar nou komt het. Hier zie je geen 418
L.

00:00:13.470 --> 00:00:13.480 align:start position:0%



00:00:13.480 --> 00:00:15.190 align:start position:0%

Goed<00:00:13.719><c> voorbeeld</c><00:00:14.200><c> doet</c><00:00:15.040><c> moeten</c>

00:00:15.190 --> 00:00:15.200 align:start position:0%
Goed voorbeeld doet moeten


00:00:15.200 --> 00:00:17.990 align:start position:0%
Goed voorbeeld doet moeten
ze bij Kia hebben gedacht.
"""

MANUAL = """WEBVTT
Kind: captions
Language: nl

00:00:00.000 --> 00:00:05.320
Ja dit logo ken je waarschijnlijk nog niet Het&nbsp;
is het logo van DON Feng

00:01:05.320 --> 00:01:12.320
5 jaar garantie &amp; 8 jaar op het accupakket
"""


class Rolling(unittest.TestCase):
    def setUp(self):
        self.segs = fetch_transcript._vtt_to_segments(ROLLING, rolling=True)

    def test_text_after_a_space_only_line_is_kept(self):
        self.assertIn({"ts": "0:13", "text": "Goed voorbeeld doet moeten"}, self.segs)

    def test_hold_cues_are_skipped_and_last_line_kept(self):
        self.assertEqual(
            [s["text"] for s in self.segs],
            ["maar nou komt het. 418", "L.", "Goed voorbeeld doet moeten", "ze bij Kia hebben gedacht."],
        )


class Manual(unittest.TestCase):
    def test_whole_cue_with_entities_unescaped(self):
        segs = fetch_transcript._vtt_to_segments(MANUAL, rolling=False)
        self.assertEqual(segs[0], {"ts": "0:00", "text": "Ja dit logo ken je waarschijnlijk nog niet Het is het logo van DON Feng"})
        self.assertEqual(segs[1], {"ts": "1:05", "text": "5 jaar garantie & 8 jaar op het accupakket"})


class KiesSpoor(unittest.TestCase):
    def test_manual_wins(self):
        info = {"language": "nl", "subtitles": {"nl": []}, "automatic_captions": {"nl": []}}
        self.assertEqual(fetch_transcript.kies_spoor(info, "nl"), "manual")

    def test_asr_only_in_the_spoken_language(self):
        info = {"language": "nl", "subtitles": {}, "automatic_captions": {"nl": [], "en": []}}
        self.assertEqual(fetch_transcript.kies_spoor(info, "nl"), "asr")

    def test_no_machine_translation(self):
        # An English video offers an automatic "nl" track too: that is a translation.
        info = {"language": "en", "subtitles": {}, "automatic_captions": {"en": [], "nl": []}}
        self.assertIsNone(fetch_transcript.kies_spoor(info, "nl"))

    def test_orig_track_counts_even_if_language_says_otherwise(self):
        # Auto-dubbed Autovisie video (2026-10-06): language en-US, but nl-orig is the original audio.
        info = {"language": "en-US", "subtitles": {}, "automatic_captions": {"nl-orig": [], "nl": [], "en-US-orig": []}}
        self.assertEqual(fetch_transcript.kies_spoor(info, "nl"), "asr")

    def test_manual_in_another_language_does_not_count(self):
        # Autovisie, 2026-10-06: manual tracks in eight languages; ask nl, get nl.
        info = {"language": "nl", "subtitles": {"en": [], "nl": []}, "automatic_captions": {}}
        self.assertEqual(fetch_transcript.kies_spoor(info, "nl"), "manual")


class MetadataFromYtdlp(unittest.TestCase):
    def test_shape_matches_the_page_scrape(self):
        info = {"id": "EFAu5nYWeCM", "title": "Kia EV2", "channel": "ANWB", "channel_id": "UCx",
                "timestamp": 1775030409, "duration": 668, "view_count": 51223, "language": "nl",
                "subtitles": {}, "automatic_captions": {"nl": []}, "categories": ["Autos & Vehicles"],
                "chapters": [{"title": "Prijs", "start_time": 114.0}], "description": "d"}
        m = fetch_transcript.metadata_from_ytdlp(info)
        self.assertEqual(m["publish_date"], "2026-04-01T08:00:09+00:00")
        self.assertEqual(m["channel_url"], "https://www.youtube.com/channel/UCx")
        self.assertEqual(m["chapters"], [{"title": "Prijs", "start": "1:54", "start_ms": 114000}])
        self.assertEqual(m["caption_tracks"], [{"language_code": "nl", "name": None, "kind": "asr", "is_translatable": True}])
        self.assertEqual((m["length_seconds"], m["view_count"], m["category"]), (668, 51223, "Autos & Vehicles"))


if __name__ == "__main__":
    unittest.main()
