"""Exact booleans on the stopping gate, and audio output that is not followed.

Each case starts from a passing fixture and breaks one thing.
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from knowledge_builder.processors.video import process_video
from knowledge_builder.research.stopping_gate import TerminationState, evaluate_stopping_gate
from .test_stopping_gate import _passing


def _not_stop(case, inp):
    """ValueError is a refusal. Any decision other than STOP is a refusal."""
    try:
        decision = evaluate_stopping_gate(inp)
    except ValueError:
        return
    case.assertNotEqual(decision.state, TerminationState.STOP_SUFFICIENT)
    case.assertIsNone(decision.certificate)


def _ffmpeg_follows(args, **kwargs):
    """Stand-in for ffmpeg: a filesystem path is written, and a symlink is followed."""
    dest = args[-1]
    if isinstance(dest, str) and "%" not in dest and not dest.startswith("pipe:"):
        Path(dest).write_bytes(b"AUDIO")
        stdout = b""
    else:
        stdout = b"AUDIO"
    return subprocess.CompletedProcess(args=args, returncode=0, stdout=stdout, stderr=b"")


class TestExactBoolsBlockStop(unittest.TestCase):
    def test_probe_none_cannot_stop(self):
        """A passing ledger stops. The same ledger with probe None must not."""
        self.assertEqual(
            evaluate_stopping_gate(_passing()).state, TerminationState.STOP_SUFFICIENT
        )
        _not_stop(self, _passing(has_viable_probe_remaining=None))

    def test_probe_non_bool_cannot_stop(self):
        """A passing ledger stops. A non-bool probe (0, not False) must not."""
        self.assertEqual(
            evaluate_stopping_gate(_passing()).state, TerminationState.STOP_SUFFICIENT
        )
        _not_stop(self, _passing(has_viable_probe_remaining=0))

    def test_probe_string_cannot_stop(self):
        """A passing ledger stops. Probe status "true" must not certify."""
        self.assertEqual(
            evaluate_stopping_gate(_passing()).state, TerminationState.STOP_SUFFICIENT
        )
        _not_stop(self, _passing(has_viable_probe_remaining="true"))

    def test_probe_missing_cannot_stop(self):
        """A passing ledger stops. Deleting the probe field must not certify."""
        self.assertEqual(
            evaluate_stopping_gate(_passing()).state, TerminationState.STOP_SUFFICIENT
        )
        inp = _passing()
        del inp.has_viable_probe_remaining
        _not_stop(self, inp)

    def test_version_yes_cannot_stop(self):
        """A passing ledger stops. Version "yes" is not exactly True."""
        self.assertEqual(
            evaluate_stopping_gate(_passing()).state, TerminationState.STOP_SUFFICIENT
        )
        _not_stop(self, _passing(is_target_version_matched="yes"))

    def test_version_one_cannot_stop(self):
        """A passing ledger stops. Version 1 is not exactly True."""
        self.assertEqual(
            evaluate_stopping_gate(_passing()).state, TerminationState.STOP_SUFFICIENT
        )
        _not_stop(self, _passing(is_target_version_matched=1))

    def test_version_missing_cannot_stop(self):
        """A passing ledger stops. Deleting the version field must not certify."""
        self.assertEqual(
            evaluate_stopping_gate(_passing()).state, TerminationState.STOP_SUFFICIENT
        )
        inp = _passing()
        del inp.is_target_version_matched
        _not_stop(self, inp)


class TestSymlinkedAudioOutputIsNotFollowed(unittest.TestCase):
    def test_symlinked_audio_output_is_not_followed(self):
        """A real output dir receives audio. audio.mp3 -> outside must not be followed."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            video = base / "talk.mp4"
            video.write_bytes(b"not-a-video")
            out = base / "extracts"
            outside = base / "outside.mp3"
            outside.write_bytes(b"ORIGINAL")

            with patch(
                "knowledge_builder.processors.video.subprocess.run",
                side_effect=_ffmpeg_follows,
            ):
                result = process_video(video, output_dir=out)
            self.assertEqual((out / "audio.mp3").read_bytes(), b"AUDIO")
            self.assertEqual(outside.read_bytes(), b"ORIGINAL")
            self.assertEqual(result["audio_path"], str(out / "audio.mp3"))

            (out / "audio.mp3").unlink()
            os.symlink(outside, out / "audio.mp3")
            with patch(
                "knowledge_builder.processors.video.subprocess.run",
                side_effect=_ffmpeg_follows,
            ):
                with self.assertRaises(Exception):
                    process_video(video, output_dir=out)
            self.assertEqual(outside.read_bytes(), b"ORIGINAL")
            self.assertTrue(os.path.islink(out / "audio.mp3"))


if __name__ == "__main__":
    unittest.main()
