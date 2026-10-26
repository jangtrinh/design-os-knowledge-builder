"""B1/B7: a concept pack may declare the version gate not applicable, with a reason.

Fixture: a ledger that passes every hard gate except the version flag.
`version_applicability: not_applicable` with a non-empty `version_reason`
passes the version gate and prints the reason. A missing, blank, or non-string
reason does not pass. The saturation label reads "low-delta rounds N/3".
"""

import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from knowledge_builder.research.stopping_gate import (
    StoppingEvaluationInput,
    TerminationState,
    evaluate_stopping_gate,
)


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


def _sha(body):
    return hashlib.sha256(body).hexdigest()


def _atom(atom_id, claim_id, rel, digest, *, claim_type="FACT", metadata=None):
    meta = {"claim": claim_id}
    meta.update(metadata or {})
    return {
        "id": atom_id,
        "run_id": "run-1",
        "claim_type": claim_type,
        "statement": f"support for {claim_id}",
        "source_uri": rel,
        "source_digest": digest,
        "captured_at": "2026-10-13T00:00:00Z",
        "confidence": "HIGH",
        "verified_by_code": False,
        "metadata": meta,
        "quote": f"frozen {atom_id}",
    }


def _fixture(root, **state_extra):
    """Everything but the version flag passes. Returns the run directory."""
    run = root / "_evidence" / "run-1"
    (run / "sources").mkdir(parents=True)
    atoms = []
    for atom_id, claim_type, meta in (
        ("c1", "FACT", {"command": "echo ok"}),
        ("fm", "FAILURE_MODE", {}),
    ):
        body = f"frozen {atom_id}\n".encode()
        rel = f"_evidence/run-1/sources/{atom_id}.txt"
        (root / rel).write_bytes(body)
        atoms.append(_atom(atom_id, "c1" if atom_id == "c1" else "other", rel, _sha(body),
                           claim_type=claim_type, metadata=meta))
    (run / "evidence.jsonl").write_text("".join(json.dumps(a) + "\n" for a in atoms), encoding="utf-8")
    state = {
        "run_id": "run-1",
        "round": 4,
        "status": "RUNNING",
        "budget_used": 0,
        "budget_total": 4,
        "remaining_budget_calls": 4,
        "gaps": [],
        "resolved": [],
        "required_claim_ids": ["c1"],
        "minimum_independent_sources": 2,
        "last_weighted_delta": 0.5,
        "consecutive_low_delta_rounds": 0,
        "researcher_runtime": "researcher-a",
    }
    state.update(state_extra)
    (run / "state.json").write_text(json.dumps(state), encoding="utf-8")
    (run / "review.json").write_text(
        json.dumps({"passed": True, "reviewer_runtime": "reviewer-b"}), encoding="utf-8"
    )
    return run


def _gate(root):
    return _run(["knowledge-builder", "gate", "--root", str(root), "--run-id", "run-1"])


def _passing(**overrides):
    base = dict(
        required_claims_total=1,
        required_claims_verified=1,
        independent_sources_count=2,
        has_execution_proof=True,
        has_counterevidence_searched=True,
        unresolved_contradictions_count=0,
        is_target_version_matched=False,
        consecutive_low_delta_rounds=3,
        last_weighted_delta=0.01,
        remaining_budget_calls=4,
        has_viable_probe_remaining=False,
        independent_review_passed=True,
    )
    base.update(overrides)
    return StoppingEvaluationInput(**base)


class TestVersionNotApplicable(unittest.TestCase):
    def test_default_ledger_reports_version_mismatch(self):
        """Control: with no declaration the version gate is not passed."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _fixture(root)
            code, out, err = _gate(root)
        self.assertEqual(code, 2, out + err)
        self.assertIn("Target library/framework version mismatch", out)

    def test_not_applicable_with_reason_passes_and_prints_reason(self):
        reason = "concept pack: no target library or framework"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _fixture(root, version_applicability="not_applicable", version_reason=reason)
            code, out, err = _gate(root)
        self.assertNotIn("version mismatch", out)
        self.assertIn(f"Version:  not applicable: {reason}", out)

    def test_not_applicable_without_reason_is_not_a_pass(self):
        for extra in (
            {"version_applicability": "not_applicable"},
            {"version_applicability": "not_applicable", "version_reason": ""},
            {"version_applicability": "not_applicable", "version_reason": "   "},
            {"version_applicability": "not_applicable", "version_reason": 7},
        ):
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                _fixture(root, **extra)
                code, out, err = _gate(root)
            self.assertEqual(code, 2, out + err)
            self.assertIn("version_reason is missing", out)

    def test_unknown_applicability_value_does_not_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _fixture(root, version_applicability="maybe", version_reason="because")
            code, out, err = _gate(root)
        self.assertEqual(code, 2, out + err)
        self.assertIn("Target library/framework version mismatch", out)

    def test_gate_can_reach_stop_when_declared_with_reason(self):
        decision = evaluate_stopping_gate(
            _passing(version_not_applicable=True, version_reason="no target library")
        )
        self.assertEqual(decision.state, TerminationState.STOP_SUFFICIENT)
        self.assertIn("no target library", decision.version_note)

    def test_declared_without_reason_cannot_stop(self):
        for reason in (None, "", "  "):
            decision = evaluate_stopping_gate(
                _passing(version_not_applicable=True, version_reason=reason)
            )
            self.assertEqual(decision.state, TerminationState.DEEPEN)
            self.assertFalse(decision.hard_gates_passed)

    def test_declared_not_applicable_never_falls_back_to_the_matched_flag(self):
        """Declared not_applicable passes only through a reason, even if matched is true."""
        for reason in (None, "", "  "):
            decision = evaluate_stopping_gate(
                _passing(is_target_version_matched=True, version_not_applicable=True, version_reason=reason)
            )
            self.assertEqual(decision.state, TerminationState.DEEPEN)
            self.assertFalse(decision.hard_gates_passed)
            self.assertIn("version_reason is missing", decision.reason)

    def test_ledger_declared_not_applicable_without_reason_ignores_matched_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _fixture(
                root,
                version_applicability="not_applicable",
                is_target_version_matched=True,
                consecutive_low_delta_rounds=3,
                last_weighted_delta=0.01,
                has_viable_probe_remaining=False,
            )
            code, out, err = _gate(root)
        self.assertEqual(code, 2, out + err)
        self.assertIn("version_reason is missing", out)

    def test_saturation_label_names_low_delta_rounds(self):
        decision = evaluate_stopping_gate(
            _passing(consecutive_low_delta_rounds=0, last_weighted_delta=0.0949)
        )
        self.assertIn("low-delta rounds 0/3", decision.reason)
        self.assertNotIn("(round ", decision.reason)

    def test_missing_measurement_label_keeps_low_delta_wording(self):
        decision = evaluate_stopping_gate(
            _passing(consecutive_low_delta_rounds=None, last_weighted_delta=None)
        )
        self.assertIn("low-delta rounds missing/3", decision.reason)


class TestExecutionNotApplicable(unittest.TestCase):
    def _no_code_fixture(self, root, **state_extra):
        run = _fixture(root, version_applicability="not_applicable", version_reason="concept pack", **state_extra)
        rows = [json.loads(line) for line in (run / "evidence.jsonl").read_text(encoding="utf-8").splitlines()]
        for row in rows:
            row["metadata"].pop("command", None)
        (run / "evidence.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        return run

    def test_default_ledger_without_command_reports_missing_execution_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._no_code_fixture(root)
            code, out, err = _gate(root)
        self.assertEqual(code, 2, out + err)
        self.assertIn("Missing code execution / test verification proof", out)

    def test_execution_not_applicable_with_reason_passes_and_prints_reason(self):
        reason = "concept pack: no executable code or CLI"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._no_code_fixture(
                root,
                execution_applicability="not_applicable",
                execution_reason=reason,
                consecutive_low_delta_rounds=3,
                last_weighted_delta=0.01,
                has_viable_probe_remaining=False,
            )
            code, out, err = _gate(root)
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("Missing code execution", out)
        self.assertIn(f"Execution: not applicable: {reason}", out)

    def test_execution_not_applicable_without_reason_is_not_a_pass(self):
        for extra in (
            {"execution_applicability": "not_applicable"},
            {"execution_applicability": "not_applicable", "execution_reason": ""},
            {"execution_applicability": "not_applicable", "execution_reason": "   "},
            {"execution_applicability": "not_applicable", "execution_reason": 7},
        ):
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self._no_code_fixture(root, **extra)
                code, out, err = _gate(root)
            self.assertEqual(code, 2, out + err)
            self.assertIn("execution_reason is missing", out)

    def test_declared_not_applicable_never_falls_back_to_has_execution_proof(self):
        for reason in (None, "", "  "):
            decision = evaluate_stopping_gate(
                _passing(has_execution_proof=True, execution_not_applicable=True, execution_reason=reason)
            )
            self.assertEqual(decision.state, TerminationState.DEEPEN)
            self.assertFalse(decision.hard_gates_passed)
            self.assertIn("execution_reason is missing", decision.reason)


if __name__ == "__main__":
    unittest.main()
