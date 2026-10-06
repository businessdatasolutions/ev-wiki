"""Offline tests for search_stills.py (targeted still search).

Run from the repo root:
    python -m unittest discover -s .claude/skills/youtube-transcript-skill/tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import extract_stills  # noqa: E402
import search_stills as ss  # noqa: E402

RAW = """\
---
title: "A talk"
video_id: abcdefghijk
length_seconds: 3725
---

## [0:00] Intro

[0:00] Welcome.
[1:05] Complexity is not complicatedness.

## [1:02:00] Close

[1:02:03] Past the hour.
"""


class ParseTranscript(unittest.TestCase):
    def test_reads_header_and_segments_in_seconds(self):
        header, segments = ss.parse_transcript(RAW)
        self.assertEqual(header["length_seconds"], 3725)
        self.assertEqual(segments, [
            (0.0, "Welcome."),
            (65.0, "Complexity is not complicatedness."),
            (3723.0, "Past the hour."),
        ])

    def test_chapter_headings_are_not_segments(self):
        _, segments = ss.parse_transcript(RAW)
        self.assertNotIn("Intro", [text for _, text in segments])


class TranscriptForPrompt(unittest.TestCase):
    def test_renders_one_timestamped_line_per_segment(self):
        text = ss.transcript_for_prompt([(65.0, "Hello."), (3723.0, "Late.")])
        self.assertEqual(text, "[1:05] Hello.\n[1:02:03] Late.")


class PadAndMerge(unittest.TestCase):
    def w(self, start, end, reason="r"):
        return {"start": start, "end": end, "reason": reason}

    def test_pads_both_sides(self):
        out = ss.pad_and_merge([self.w(100, 110)], pad=30, duration=1000)
        self.assertEqual((out[0]["start"], out[0]["end"]), (70, 140))

    def test_clamps_to_video(self):
        out = ss.pad_and_merge([self.w(10, 20), self.w(980, 995)], pad=30, duration=1000)
        self.assertEqual((out[0]["start"], out[-1]["end"]), (0, 1000))

    def test_merges_overlapping_windows_and_keeps_both_reasons(self):
        out = ss.pad_and_merge([self.w(100, 110, "a"), self.w(150, 160, "b")], pad=30, duration=1000)
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0]["start"], out[0]["end"]), (70, 190))
        self.assertEqual(out[0]["reason"], "a; b")

    def test_keeps_distant_windows_apart_in_time_order(self):
        out = ss.pad_and_merge([self.w(800, 810, "late"), self.w(100, 110, "early")], pad=30, duration=1000)
        self.assertEqual([x["reason"] for x in out], ["early", "late"])


class Subtract(unittest.TestCase):
    def test_cuts_out_the_part_already_searched(self):
        got = ss.subtract([{"start": 0.0, "end": 100.0, "reason": "r"}], [{"start": 20.0, "end": 40.0}])
        self.assertEqual([(w["start"], w["end"]) for w in got], [(0.0, 20.0), (40.0, 100.0)])
        self.assertEqual({w["reason"] for w in got}, {"r"})

    def test_drops_a_window_that_was_searched_entirely(self):
        got = ss.subtract([{"start": 30.0, "end": 50.0, "reason": "r"}], [{"start": 20.0, "end": 60.0}])
        self.assertEqual(got, [])

    def test_drops_slivers_too_short_to_hold_a_visual(self):
        got = ss.subtract([{"start": 0.0, "end": 100.0, "reason": "r"}], [{"start": 2.0, "end": 100.0}])
        self.assertEqual(got, [])


class ToOffset(unittest.TestCase):
    def test_whole_seconds(self):
        self.assertEqual(ss.to_offset(200.0), "200s")

    def test_fractional_seconds(self):
        self.assertEqual(ss.to_offset(10.5), "10.5s")


class ResolveTimes(unittest.TestCase):
    WINDOW = {"start": 600.0, "end": 660.0}

    def test_absolute_times_inside_the_window_are_kept(self):
        got = ss.resolve_times({"start": "10:10", "end": "10:20"}, self.WINDOW)
        self.assertEqual(got, (610.0, 620.0, "absolute"))

    def test_times_within_window_length_are_read_as_relative(self):
        got = ss.resolve_times({"start": "0:10", "end": "0:20"}, self.WINDOW)
        self.assertEqual(got, (610.0, 620.0, "relative"))

    def test_times_outside_both_readings_are_rejected(self):
        self.assertIsNone(ss.resolve_times({"start": "30:00", "end": "30:10"}, self.WINDOW))

    def test_unparseable_times_are_rejected(self):
        self.assertIsNone(ss.resolve_times({"start": "about ten", "end": "10:20"}, self.WINDOW))

    def test_fractional_seconds_are_read_not_dropped(self):
        # Seen live 2026-10-03: Gemini answered "10:55.000" / "11:00.500" for a
        # window and all seven matches in it were skipped as unparseable.
        got = ss.resolve_times({"start": "10:05.000", "end": "10:10.500"}, self.WINDOW)
        self.assertEqual(got, (605.0, 610.5, "absolute"))

    def test_hour_timestamps_with_fractions(self):
        got = ss.resolve_times({"start": "1:00:05.25", "end": "1:00:09"}, {"start": 3600.0, "end": 3660.0})
        self.assertEqual(got, (3605.25, 3609.0, "absolute"))

    def test_end_before_start_is_raised_to_start(self):
        got = ss.resolve_times({"start": "10:20", "end": "10:10"}, self.WINDOW)
        self.assertEqual(got, (620.0, 620.0, "absolute"))

    def test_minutes_past_99_are_read_not_dropped(self):
        # Seen live 2026-10-03 on an 8-hour stream: for two windows Gemini wrote
        # "127:09" for 2:07:09 and "345:36" for 5:45:36, and all 30 matches in
        # them were skipped as unparseable.
        window = {"start": 7629.0, "end": 8029.0}  # 2:07:09-2:13:49
        got = ss.resolve_times({"start": "127:09", "end": "127:12.5"}, window)
        self.assertEqual(got, (7629.0, 7632.5, "absolute"))


class ParseWindowsArg(unittest.TestCase):
    def test_reads_comma_separated_ranges(self):
        got = ss.parse_windows_arg("3:20-4:20,1:00:00-1:01:30")
        self.assertEqual([(w["start"], w["end"]) for w in got], [(200.0, 260.0), (3600.0, 3690.0)])
        self.assertEqual({w["reason"] for w in got}, {"set by hand (--windows)"})

    def test_rejects_malformed_range(self):
        with self.assertRaises(ValueError):
            ss.parse_windows_arg("3:20 to 4:20")


class OutputPaths(unittest.TestCase):
    def test_search_outputs_sit_beside_not_on_top_of_full_scan_outputs(self):
        stills_dir, manifest = ss.output_paths(Path("/repo"), "a-talk", "Diagrams on complexity vs. complicatedness")
        self.assertEqual(stills_dir, Path("/repo/raw/images/a-talk/search-diagrams-on-complexity-vs-complicatedness"))
        self.assertEqual(manifest, Path("/repo/raw/videos/a-talk.search-diagrams-on-complexity-vs-complicatedness.stills.md"))

    def test_full_scan_cleanup_never_matches_the_search_folder(self):
        # extract_stills.py deletes files in raw/images/<slug>/ that match STILL_RE
        # before a re-run. The search folder must never look like one of them.
        stills_dir, _ = ss.output_paths(Path("/repo"), "a-talk", "01 diagrams")
        self.assertIsNone(extract_stills.STILL_RE.match(stills_dir.name))


class RenderManifest(unittest.TestCase):
    def test_records_query_windows_and_match_reasons(self):
        text = ss.render_search_manifest(
            slug="a-talk", video_id="abcdefghijk", url="https://www.youtube.com/watch?v=abcdefghijk",
            title="A talk", channel="Chan", duration=3725, query="complexity diagrams",
            stills_rel="../images/a-talk/search-complexity-diagrams/",
            windows=[{"start": 35.0, "end": 125.0, "reason": "defines both terms", "stage": "located"}],
            stills=[{"n": 1, "at": 64.0, "start_s": 60.0, "end_s": 65.0, "file": "01-01m04-x.png",
                     "kind": "chart", "title": "Index", "content": "A -> B", "adds": "the numbers",
                     "match": "plots complexity against complicatedness", "stage": "located",
                     "time_basis": "absolute"}],
            skipped=[], extractor={"model": "m", "fps": 2}, usage={"total_tokens": 10},
        )
        self.assertIn("query: complexity diagrams", text)
        self.assertIn("defines both terms", text)
        self.assertIn("plots complexity against complicatedness", text)
        self.assertIn("../images/a-talk/search-complexity-diagrams/01-01m04-x.png", text)
        self.assertIn("unverified", text.lower())


if __name__ == "__main__":
    unittest.main()
