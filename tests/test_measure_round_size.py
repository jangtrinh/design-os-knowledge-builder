"""Novelty is quote history. A round under five atoms does not move the low-delta streak.

metadata.novel is ignored. A quote that already appeared in an earlier round,
including a backfill atom, is not novel. Two atoms in the same round may share
a quote and both still count. A round with fewer than five non-backfill atoms
is printed and left out of the trailing streak.
"""

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def _run(argv):
    import knowledge_builder.cli as cli_mod

    stdout, stderr = io.StringIO(), io.StringIO()
    with patch("sys.argv", argv), patch("sys.stdout", stdout), patch("sys.stderr", stderr):
        try:
            cli_mod.main()
            code = 0
        except SystemExit as caught:
            code = caught.code
    return code, stdout.getvalue(), stderr.getvalue()


def _atom(atom_id, rnd, quote, novel=False, backfill=False):
    meta = {"round": rnd, "novel": novel}
    if backfill:
        meta["backfill"] = True
    return {
        "id": atom_id,
        "run_id": "run-1",
        "claim_type": "FACT",
        "statement": f"statement {atom_id}",
        "source_uri": "_evidence/run-1/sources/s.txt",
        "source_digest": "a" * 64,
        "captured_at": "2026-10-13T00:00:00Z",
        "confidence": "HIGH",
        "verified_by_code": False,
        "metadata": meta,
        "quote": quote,
    }


def _measure(atoms):
    with tempfile.TemporaryDirectory() as tmp:
        code, out, err = _run(
            ["knowledge-builder", "run", "init", "--root", tmp, "--id", "run-1", "--budget", "5"]
        )
        assert code == 0, out + err
        run = Path(tmp) / "_evidence" / "run-1"
        (run / "evidence.jsonl").write_text("".join(json.dumps(a) + "\n" for a in atoms), encoding="utf-8")
        return _run(["knowledge-builder", "run", "measure", "--root", tmp, "--id", "run-1"])


class TestMeasureRoundSize(unittest.TestCase):
    def test_novelty_follows_quote_history_and_small_rounds_do_not_move_the_streak(self):
        """Flags say the opposite of the quotes. The count follows the quotes.

        Round 1 repeats q1 inside the round, so both copies are novel, and a
        backfill atom plants q-seen for later. Round 2 reuses every quote and
        sets novel true; none of those atoms are new. Round 3 has three new
        quotes and is too small to extend or reset the streak round 2 started.
        """
        atoms = [
            _atom("a1", 1, "q1", novel=False),
            _atom("a1b", 1, "q1", novel=False),
            _atom("a2", 1, "q2", novel=False),
            _atom("a3", 1, "q3", novel=False),
            _atom("a4", 1, "q4", novel=False),
            _atom("back", 1, "q-seen", novel=False, backfill=True),
            _atom("b1", 2, "q1", novel=True),
            _atom("b2", 2, "q2", novel=True),
            _atom("b3", 2, "q3", novel=True),
            _atom("b4", 2, "q4", novel=True),
            _atom("b5", 2, "q-seen", novel=True),
            _atom("c1", 3, "fresh-one", novel=False),
            _atom("c2", 3, "fresh-two", novel=False),
            _atom("c3", 3, "fresh-three", novel=False),
        ]
        code, out, err = _measure(atoms)
        self.assertEqual(code, 0, out + err)
        self.assertIn("round 1: atoms 5, novel 5, before 0, delta n/a (baseline)", out)
        self.assertIn("round 2: atoms 5, novel 0, before 5, delta 0.0000", out)
        self.assertIn("round 3: atoms 3, novel 3, before 10, delta 0.3000 (too small: 3 < 5, not counted)", out)
        self.assertIn("consecutive_low_delta_rounds=1 last_weighted_delta=0.0", out)
        self.assertIn("backfill atoms: 1 (excluded)", out)
