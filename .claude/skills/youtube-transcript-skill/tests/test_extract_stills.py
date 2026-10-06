"""Offline tests for extract_stills.py (full still scan).

Run from the repo root:
    python -m unittest discover -s .claude/skills/youtube-transcript-skill/tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import extract_stills  # noqa: E402


class Window(unittest.TestCase):
    def test_whole_seconds(self):
        self.assertEqual(extract_stills._window({"start": "10:55", "end": "11:00"}, 3000), (655.0, 660.0))

    def test_fractional_seconds_are_read_not_dropped(self):
        # Gemini sometimes writes "10:55.000". Seen live 2026-10-03 in the
        # search script, where it dropped every match in a window.
        got = extract_stills._window({"start": "10:55.000", "end": "11:00.500"}, 3000)
        self.assertEqual(got, (655.0, 660.5))

    def test_hour_timestamps_with_fractions(self):
        got = extract_stills._window({"start": "1:00:05.25", "end": "1:00:09"}, 4000)
        self.assertEqual(got, (3605.25, 3609.0))

    def test_unparseable_times_are_rejected(self):
        self.assertIsNone(extract_stills._window({"start": "about ten", "end": "11:00"}, 3000))

    def test_start_past_the_end_of_the_video_is_rejected(self):
        self.assertIsNone(extract_stills._window({"start": "60:00", "end": "60:05"}, 3000))

    def test_end_is_kept_inside_the_video(self):
        self.assertEqual(extract_stills._window({"start": "49:50", "end": "55:00"}, 3000), (2990.0, 2999.5))


class FrameSourceTests(unittest.TestCase):
    """Frames come from seeking the stream; a full download is only the fallback.

    On an 8-hour stream (2026-10-03) every run downloaded 3.4 GB to cut a few
    dozen frames. Seeking the stream URL grabbed 18 frames in 34 s instead.
    """
    STREAM = "https://example.invalid/videoplayback?itag=298"
    LOCAL = Path("/tmp/video.mp4")

    def setUp(self):
        self.sources: list = []
        self.downloads = 0

    def _download(self):
        self.downloads += 1
        return self.LOCAL

    def _grab_ok(self, source, at_s, out):
        self.sources.append(source)

    def _grab_stream_fails(self, source, at_s, out):
        if source == self.STREAM:
            raise extract_stills.subprocess.CalledProcessError(1, "ffmpeg")
        self.sources.append(source)

    def test_grabs_from_the_stream_without_downloading(self):
        frames = extract_stills.FrameSource(self.STREAM, self._download, grab=self._grab_ok)
        for at in (10.0, 20.0, 30.0):
            frames.grab(at, Path(f"/tmp/{at}.png"))
        self.assertEqual(self.sources, [self.STREAM] * 3)
        self.assertEqual(self.downloads, 0)

    def test_a_failed_seek_falls_back_to_one_download_for_the_rest(self):
        frames = extract_stills.FrameSource(self.STREAM, self._download, grab=self._grab_stream_fails)
        for at in (10.0, 20.0, 30.0):
            frames.grab(at, Path(f"/tmp/{at}.png"))
        self.assertEqual(self.sources, [self.LOCAL] * 3)
        self.assertEqual(self.downloads, 1)

    def test_without_a_stream_url_it_downloads_once(self):
        frames = extract_stills.FrameSource(None, self._download, grab=self._grab_ok)
        for at in (10.0, 20.0):
            frames.grab(at, Path(f"/tmp/{at}.png"))
        self.assertEqual(self.sources, [self.LOCAL] * 2)
        self.assertEqual(self.downloads, 1)


if __name__ == "__main__":
    unittest.main()
