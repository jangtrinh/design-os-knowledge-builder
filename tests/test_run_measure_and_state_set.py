"""B2/B3: `run measure` derives saturation from the ledger; `run state set` writes typed state.

Fixture: round 1 has 4 atoms (baseline). Round 2 has 2 atoms, 1 novel (1/4 = 0.25).
Round 3 has 3 atoms, 0 novel (0/6 = 0.0). With --material only a novel atom whose
quote a module anchor cites counts. Nothing is written without --write-state.
"""

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def _run(argv, stdin=""):
    import knowledge_builder.cli as cli_mod

    stdout = io.StringIO()
    stderr = io.StringIO()
    with (
        patch("sys.argv", argv),
        patch("sys.stdout", stdout),
        patch("sys.stderr", stderr),
        patch("sys.stdin", io.StringIO(stdin)),
    ):
        try:
            cli_mod.main()
            code = 0
        except SystemExit as caught:
            code = caught.code
    return code, stdout.getvalue(), stderr.getvalue()


def _atom(atom_id, rnd, novel, quote):
    meta = {}
    if rnd is not None:
        meta["round"] = rnd
    if novel is not None:
        meta["novel"] = novel
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


ATOMS = [
    _atom("a1", 1, False, "q-a1"),
    _atom("a2", None, False, "q-a2"),  # no round means round 1
    _atom("a3", 1, False, "q-a3"),
    _atom("a4", 1, False, "q-a4"),
    _atom("b1", 2, True, "q-b1"),
    _atom("b2", 2, False, "q-b2"),
    _atom("c1", 3, False, "q-c1"),
    _atom("c2", 3, False, "q-c2"),
    _atom("c3", 3, False, "q-c3"),
]
MODULE = """---
id: m
---
# M

## Core Knowledge Content

Cited. <!-- ease:source uri=x sha256=y quote="q-b1" -->
Cited with single quotes. <!-- ease:source uri=x sha256=y quote='q-b2' -->
"""


def _init(root, atoms=ATOMS, module=MODULE):
    code, out, err = _run(
        ["knowledge-builder", "run", "init", "--root", str(root), "--id", "run-1", "--budget", "5"]
    )
    assert code == 0, out + err
    run = Path(root) / "_evidence" / "run-1"
    (run / "evidence.jsonl").write_text(
        "".join(json.dumps(a) + "\n" for a in atoms), encoding="utf-8"
    )
    (Path(root) / "m.md").write_text(module, encoding="utf-8")
    return run


def _state(run):
    return json.loads((run / "state.json").read_text(encoding="utf-8"))


def _measure(root, *extra):
    return _run(["knowledge-builder", "run", "measure", "--root", str(root), "--id", "run-1", *extra])


def _set(root, key, value):
    return _run(
        ["knowledge-builder", "run", "state", "set", "--root", str(root), "--id", "run-1",
         "--key", key, "--value", value]
    )


class TestRunMeasure(unittest.TestCase):
    def test_measure_prints_per_round_delta_and_trailing_low_rounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            _init(tmp)
            code, out, err = _measure(tmp)
        self.assertEqual(code, 0, out + err)
        self.assertIn("round 1: atoms 4, novel 0, before 0, delta n/a (baseline)", out)
        self.assertIn("round 2: atoms 2, novel 1, before 4, delta 0.2500", out)
        self.assertIn("round 3: atoms 3, novel 0, before 6, delta 0.0000", out)
        self.assertIn("consecutive_low_delta_rounds=1 last_weighted_delta=0.0", out)

    def test_material_counts_only_novel_atoms_cited_by_an_anchor(self):
        atoms = ATOMS + [_atom("b3", 2, True, "q-uncited")]
        with tempfile.TemporaryDirectory() as tmp:
            _init(tmp, atoms=atoms)
            _, plain, _ = _measure(tmp)
            code, out, err = _measure(tmp, "--material")
        self.assertIn("round 2: atoms 3, novel 2, before 4, delta 0.5000", plain)
        self.assertEqual(code, 0, out + err)
        self.assertIn("round 2: atoms 3, novel 1, before 4, delta 0.2500", out)

    def test_material_ignores_a_quote_that_only_sits_in_a_code_fence(self):
        module = MODULE + "\n```\n<!-- ease:source uri=x sha256=y quote=\"q-b3\" -->\n```\n"
        atoms = ATOMS + [_atom("b3", 2, True, "q-b3")]
        with tempfile.TemporaryDirectory() as tmp:
            _init(tmp, atoms=atoms, module=module)
            _, out, _ = _measure(tmp, "--material")
        self.assertIn("round 2: atoms 3, novel 1, before 4, delta 0.2500", out)

    def test_measure_writes_nothing_unless_write_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = _init(tmp)
            before = (run / "state.json").read_bytes()
            _measure(tmp)
            self.assertEqual((run / "state.json").read_bytes(), before)
            code, out, err = _measure(tmp, "--write-state")
            self.assertEqual(code, 0, out + err)
            state = _state(run)
        self.assertEqual(state["consecutive_low_delta_rounds"], 1)
        self.assertEqual(state["last_weighted_delta"], 0.0)
        self.assertEqual(state["required_claim_ids"], [])
        self.assertEqual(state["budget_total"], 5)

    def test_write_state_with_only_a_baseline_round_writes_nothing(self):
        atoms = [a for a in ATOMS if a["metadata"].get("round", 1) == 1]
        with tempfile.TemporaryDirectory() as tmp:
            run = _init(tmp, atoms=atoms)
            before = (run / "state.json").read_bytes()
            code, out, err = _measure(tmp, "--write-state")
            self.assertEqual(code, 0, out + err)
            self.assertEqual((run / "state.json").read_bytes(), before)
        self.assertIn("nothing to write", out)

    def test_a_delta_above_the_threshold_resets_the_trailing_count(self):
        atoms = ATOMS + [_atom("d1", 4, True, "q-d1")]
        with tempfile.TemporaryDirectory() as tmp:
            _init(tmp, atoms=atoms)
            _, out, _ = _measure(tmp)
        self.assertIn("consecutive_low_delta_rounds=0", out)

    def test_measure_on_an_uninitialised_run_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = _measure(tmp)
        self.assertEqual(code, 1)
        self.assertIn("run is not initialized", err)


class TestRecordRoundMetadata(unittest.TestCase):
    def _record(self, tmp, metadata):
        atom = _atom("x1", None, None, "q")
        atom["metadata"] = metadata
        return _run(
            ["knowledge-builder", "run", "record", "--root", str(tmp), "--id", "run-1"],
            stdin=json.dumps(atom),
        )

    def test_round_and_novel_are_typed(self):
        for bad in ({"round": "2"}, {"round": 0}, {"round": True}, {"round": 1.5}, {"novel": "yes"}, {"novel": 1}):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as tmp:
                run = _init(tmp, atoms=[])
                code, out, err = self._record(tmp, bad)
                self.assertEqual(code, 1, out + err)
                self.assertIn("invalid atom", err)
                self.assertEqual((run / "evidence.jsonl").read_text(), "")

    def test_valid_round_and_novel_are_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = _init(tmp, atoms=[])
            code, out, err = self._record(tmp, {"round": 2, "novel": True})
            self.assertEqual(code, 0, out + err)
            line = json.loads((run / "evidence.jsonl").read_text().splitlines()[0])
        self.assertEqual(line["metadata"], {"round": 2, "novel": True})


class TestRunStateSet(unittest.TestCase):
    def test_typed_keys_round_trip(self):
        cases = (
            ("round", "5", 5),
            ("consecutive_low_delta_rounds", "2", 2),
            ("last_weighted_delta", "0.0949", 0.0949),
            ("has_viable_probe_remaining", "false", False),
            ("has_viable_probe_remaining", "true", True),
            ("is_target_version_matched", "true", True),
            ("version_applicability", "not_applicable", "not_applicable"),
            ("version_reason", "concept pack: no target library", "concept pack: no target library"),
        )
        for key, raw, expected in cases:
            with self.subTest(key=key, raw=raw), tempfile.TemporaryDirectory() as tmp:
                run = _init(tmp, atoms=[])
                code, out, err = _set(tmp, key, raw)
                self.assertEqual(code, 0, out + err)
                value = _state(run)[key]
                self.assertEqual(value, expected)
                self.assertIs(type(value), type(expected))

    def test_invalid_values_are_refused_and_state_is_unchanged(self):
        bad = (
            ("round", "-1"), ("round", "x"), ("round", "1.5"), ("round", "True"),
            ("consecutive_low_delta_rounds", "-2"),
            ("last_weighted_delta", "nan"), ("last_weighted_delta", "-0.1"), ("last_weighted_delta", "inf"),
            ("has_viable_probe_remaining", "yes"), ("has_viable_probe_remaining", "True"),
            ("is_target_version_matched", "1"),
            ("version_applicability", "maybe"),
            ("version_reason", "   "), ("version_reason", ""),
            ("resolved", ""),
        )
        for key, raw in bad:
            with self.subTest(key=key, raw=raw), tempfile.TemporaryDirectory() as tmp:
                run = _init(tmp, atoms=[])
                before = (run / "state.json").read_bytes()
                code, out, err = _set(tmp, key, raw)
                self.assertEqual(code, 1, out + err)
                self.assertEqual((run / "state.json").read_bytes(), before)

    def test_frozen_and_unknown_keys_are_refused(self):
        for key in ("required_claim_ids", "remaining_budget_calls", "minimum_independent_sources",
                    "researcher_runtime", "status", "nonsense"):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as tmp:
                run = _init(tmp, atoms=[])
                before = (run / "state.json").read_bytes()
                code, out, err = _set(tmp, key, "1")
                self.assertEqual(code, 1, out + err)
                self.assertIn("not a settable key", err)
                self.assertEqual((run / "state.json").read_bytes(), before)

    def test_resolved_appends_without_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = _init(tmp, atoms=[])
            self.assertEqual(_set(tmp, "resolved", "hc-19")[0], 0)
            self.assertEqual(_set(tmp, "resolved", "hd-3")[0], 0)
            self.assertEqual(_set(tmp, "resolved", "hc-19")[0], 0)
            self.assertEqual(_state(run)["resolved"], ["hc-19", "hd-3"])

    def test_set_keeps_other_state_and_the_gate_reads_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = _init(tmp, atoms=[])
            _set(tmp, "version_applicability", "not_applicable")
            _set(tmp, "version_reason", "concept pack")
            state = _state(run)
        self.assertEqual(state["version_applicability"], "not_applicable")
        self.assertEqual(state["version_reason"], "concept pack")
        self.assertEqual(state["budget_total"], 5)

    def test_set_on_an_uninitialised_run_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = _set(tmp, "round", "1")
        self.assertEqual(code, 1)
        self.assertIn("run is not initialized", err)


if __name__ == "__main__":
    unittest.main()
