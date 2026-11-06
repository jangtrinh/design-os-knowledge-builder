"""A contradiction is resolved by appending a reason, not by a legacy string list."""

import json
import tempfile
import unittest
from pathlib import Path

from tests.test_ontology_support import run_cli


def _init(root):
    code, out, err = run_cli(
        ["knowledge-builder", "run", "init", "--root", str(root), "--id", "r1", "--budget", "4", "--require", "c1"]
    )
    assert code == 0, out + err


def _ready(root, **extra):
    path = root / "_evidence" / "r1" / "state.json"
    state = json.loads(path.read_text(encoding="utf-8"))
    state.update({
        "last_weighted_delta": 0.01,
        "consecutive_low_delta_rounds": 3,
        "has_viable_probe_remaining": True,
        "is_target_version_matched": True,
        "researcher_runtime": "researcher-a",
    })
    state.update(extra)
    path.write_text(json.dumps(state), encoding="utf-8")
    return path


def _contradiction(root, ident="cx"):
    atom = {
        "id": ident, "run_id": "r1", "claim_type": "CONTRADICTION", "statement": "sides disagree on scope",
        "source_uri": "_evidence/r1/sources/missing.txt", "source_digest": "a" * 64,
        "captured_at": "2026-10-13T05:00:00+00:00", "confidence": "HIGH", "verified_by_code": False,
        "metadata": {"claim": "c-contra"}, "quote": "sides disagree on the measured scope of the claim.",
    }
    with (root / "_evidence" / "r1" / "evidence.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(atom) + "\n")


def _gate(root):
    return run_cli(["knowledge-builder", "gate", "--root", str(root), "--run-id", "r1"])


class RunResolveTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "root"
        self.root.mkdir()
        _init(self.root)

    def test_state_set_resolved_is_refused(self):
        path = self.root / "_evidence" / "r1" / "state.json"
        before = path.read_bytes()
        code, out, err = run_cli(
            ["knowledge-builder", "run", "state", "set", "--root", str(self.root), "--id", "r1", "--key", "resolved", "--value", "cx"]
        )
        self.assertEqual(code, 1)
        self.assertIn("not a settable key", err)
        self.assertEqual(path.read_bytes(), before)

    def test_resolve_appends_a_reason(self):
        _contradiction(self.root)
        _ready(self.root)
        code, out, err = run_cli(
            ["knowledge-builder", "run", "resolve", "--root", str(self.root), "--id", "r1", "--atom", "cx", "--reason", "scopes differ"]
        )
        self.assertEqual(code, 0, out + err)
        state = json.loads((self.root / "_evidence" / "r1" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["resolutions"], [{"atom": "cx", "reason": "scopes differ"}])
        code, out, err = _gate(self.root)
        self.assertNotIn("Unresolved contradictions", out)

    def test_blank_reason_leaves_state_unchanged(self):
        _contradiction(self.root)
        path = _ready(self.root)
        before = path.read_bytes()
        code, out, err = run_cli(
            ["knowledge-builder", "run", "resolve", "--root", str(self.root), "--id", "r1", "--atom", "cx", "--reason", "   "]
        )
        self.assertNotEqual(code, 0)
        self.assertNotIn("invalid choice", err)
        self.assertEqual(path.read_bytes(), before)

    def test_non_contradiction_is_refused(self):
        atom = {
            "id": "a1", "run_id": "r1", "claim_type": "FACT", "statement": "a fact",
            "source_uri": "_evidence/r1/sources/missing.txt", "source_digest": "b" * 64,
            "captured_at": "2026-10-13T05:00:00+00:00", "confidence": "HIGH", "verified_by_code": False,
            "metadata": {}, "quote": "Alpha holds in every case across the measured range.",
        }
        with (self.root / "_evidence" / "r1" / "evidence.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(atom) + "\n")
        path = _ready(self.root)
        before = path.read_bytes()
        code, out, err = run_cli(
            ["knowledge-builder", "run", "resolve", "--root", str(self.root), "--id", "r1", "--atom", "a1", "--reason", "not a contradiction"]
        )
        self.assertNotEqual(code, 0)
        self.assertNotIn("invalid choice", err)
        self.assertEqual(path.read_bytes(), before)

    def test_legacy_resolved_list_is_ignored(self):
        _contradiction(self.root)
        _ready(self.root, resolved=["cx"])
        code, out, err = _gate(self.root)
        self.assertIn("Unresolved contradictions (1)", out)
        self.assertIn("ignored legacy resolved entries: 1", out)

    def test_resolutions_entry_clears_the_contradiction(self):
        _contradiction(self.root)
        _ready(self.root, resolutions=[{"atom": "cx", "reason": "scopes differ"}])
        code, out, err = _gate(self.root)
        self.assertNotIn("Unresolved contradictions", out)
        self.assertNotIn("ignored legacy resolved entries:", out)

    def test_blank_resolution_reason_does_not_clear(self):
        _contradiction(self.root)
        _ready(self.root, resolutions=[{"atom": "cx", "reason": "  "}])
        code, out, err = _gate(self.root)
        self.assertIn("Unresolved contradictions (1)", out)
