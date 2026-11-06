"""Saturation is measured. run state set does not declare it.

consecutive_low_delta_rounds and last_weighted_delta are written only by
run measure --write-state. state set refuses those keys and leaves state.json
byte-identical.
"""

import tempfile
import unittest

from tests.test_run_measure_and_state_set import _init, _set


class TestSaturationIsMeasuredNotSet(unittest.TestCase):
    def test_state_set_refuses_measured_saturation_keys(self):
        for key in ("consecutive_low_delta_rounds", "last_weighted_delta"):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as tmp:
                run = _init(tmp, atoms=[])
                before = (run / "state.json").read_bytes()
                code, out, err = _set(tmp, key, "1")
                self.assertEqual(code, 1, out + err)
                self.assertIn("run measure --write-state", err)
                self.assertNotIn("not a settable key", err)
                self.assertEqual((run / "state.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
