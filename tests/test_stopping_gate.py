"""Test Stopping Gate logic across the 11 core scenarios formulated by Codex Native Astra."""

import unittest
from knowledge_builder.research.stopping_gate import evaluate_stopping_gate, StoppingEvaluationInput, TerminationState


def _passing(**overrides):
    """One sufficient ledger. Negative tests override exactly one field."""
    base = dict(
        required_claims_total=5,
        required_claims_verified=5,
        independent_sources_count=3,
        has_execution_proof=True,
        has_counterevidence_searched=True,
        unresolved_contradictions_count=0,
        is_target_version_matched=True,
        consecutive_low_delta_rounds=3,
        last_weighted_delta=0.015,
        remaining_budget_calls=5,
        has_viable_probe_remaining=False,
        independent_review_passed=True,
    )
    base.update(overrides)
    return StoppingEvaluationInput(**base)


class TestStoppingGateScenarios(unittest.TestCase):

    def test_scenario_1_sufficient_evidence(self):
        """Scenario 1: All hard gates pass + saturation reached -> STOP_SUFFICIENT."""
        res = evaluate_stopping_gate(_passing())
        self.assertEqual(res.state, TerminationState.STOP_SUFFICIENT)
        self.assertTrue(res.hard_gates_passed)
        self.assertTrue(res.saturation_passed)
        self.assertIsNotNone(res.certificate)

    def test_scenario_2_low_delta_but_missing_critical_claims(self):
        """Scenario 2: Only the missing claims differ from a passing ledger -> DEEPEN."""
        res = evaluate_stopping_gate(_passing(required_claims_verified=3))
        self.assertEqual(res.state, TerminationState.DEEPEN)
        self.assertFalse(res.hard_gates_passed)

    def test_scenario_3_many_urls_same_origin(self):
        """Scenario 3: Only the source count differs from a passing ledger -> DEEPEN."""
        res = evaluate_stopping_gate(_passing(independent_sources_count=1))
        self.assertEqual(res.state, TerminationState.DEEPEN)

    def test_scenario_4_marketing_no_execution_proof(self):
        """Scenario 4: Only execution proof differs from a passing ledger -> DEEPEN."""
        res = evaluate_stopping_gate(_passing(has_execution_proof=False))
        self.assertEqual(res.state, TerminationState.DEEPEN)

    def test_scenario_5_unresolved_contradictions(self):
        """Scenario 5: Only unresolved contradictions differ from a passing ledger -> DEEPEN."""
        res = evaluate_stopping_gate(_passing(unresolved_contradictions_count=2))
        self.assertEqual(res.state, TerminationState.DEEPEN)

    def test_scenario_6_version_drift(self):
        """Scenario 6: Only the version flag differs from a passing ledger -> DEEPEN."""
        res = evaluate_stopping_gate(_passing(is_target_version_matched=False))
        self.assertEqual(res.state, TerminationState.DEEPEN)

    def test_scenario_7_missing_counterevidence_search(self):
        """Scenario 7: Only counterevidence differs from a passing ledger -> DEEPEN."""
        res = evaluate_stopping_gate(_passing(has_counterevidence_searched=False))
        self.assertEqual(res.state, TerminationState.DEEPEN)

    def test_f13_only_a_remaining_probe_blocks_stop(self):
        """A passing ledger with one probe left must not stop."""
        res = evaluate_stopping_gate(_passing(has_viable_probe_remaining=True))
        self.assertNotEqual(res.state, TerminationState.STOP_SUFFICIENT)
        self.assertIsNone(res.certificate)

    def test_scenario_8_blocked_upstream(self):
        """Scenario 8: Blocked by paywall or anti-scraping -> ABSTAIN_BLOCKED."""
        inp = StoppingEvaluationInput(
            required_claims_total=5,
            required_claims_verified=2,
            independent_sources_count=1,
            has_execution_proof=False,
            has_counterevidence_searched=False,
            unresolved_contradictions_count=0,
            is_target_version_matched=True,
            consecutive_low_delta_rounds=0,
            last_weighted_delta=0.5,
            remaining_budget_calls=5,
            has_viable_probe_remaining=False,
            is_blocked=True,
            block_reason="Cloudflare 403 on target portal",
        )
        res = evaluate_stopping_gate(inp)
        self.assertEqual(res.state, TerminationState.ABSTAIN_BLOCKED)

    def test_scenario_9_budget_exhausted_still_deficient(self):
        """Scenario 9: Budget runs out while claims are still missing -> PAUSE_BUDGET."""
        inp = StoppingEvaluationInput(
            required_claims_total=5,
            required_claims_verified=3,
            independent_sources_count=2,
            has_execution_proof=True,
            has_counterevidence_searched=True,
            unresolved_contradictions_count=0,
            is_target_version_matched=True,
            consecutive_low_delta_rounds=2,
            last_weighted_delta=0.05,
            remaining_budget_calls=0,  # Budget 0
            has_viable_probe_remaining=True,
        )
        res = evaluate_stopping_gate(inp)
        self.assertEqual(res.state, TerminationState.PAUSE_BUDGET)

    def test_cli_defaults_are_not_stop_sufficient(self):
        """Bare `gate` builds StoppingEvaluationInput from CLI defaults and must not certify."""
        import io
        from unittest.mock import patch

        import knowledge_builder.cli as cli_mod

        captured = {}

        def spy(inp):
            captured["decision"] = evaluate_stopping_gate(inp)
            return captured["decision"]

        with patch.object(cli_mod, "evaluate_stopping_gate", spy), patch(
            "sys.argv", ["knowledge-builder", "gate"]
        ), patch("sys.stdout", io.StringIO()), patch("sys.stderr", io.StringIO()):
            try:
                cli_mod.main()
            except SystemExit:
                pass

        self.assertIn("decision", captured)
        self.assertNotEqual(captured["decision"].state, TerminationState.STOP_SUFFICIENT)

    def test_review_false_and_no_probe_is_not_stop_sufficient(self):
        """Hard gates and saturation without an independent review do not stop."""
        inp = StoppingEvaluationInput(
            required_claims_total=5,
            required_claims_verified=5,
            independent_sources_count=3,
            has_execution_proof=True,
            has_counterevidence_searched=True,
            unresolved_contradictions_count=0,
            is_target_version_matched=True,
            consecutive_low_delta_rounds=3,
            last_weighted_delta=0.01,
            remaining_budget_calls=5,
            has_viable_probe_remaining=False,
            independent_review_passed=False,
        )
        res = evaluate_stopping_gate(inp)
        self.assertNotEqual(res.state, TerminationState.STOP_SUFFICIENT)
        self.assertIsNone(res.certificate)


class TestGateExitCodes(unittest.TestCase):
    def _run(self, argv):
        import io
        from unittest.mock import patch

        import knowledge_builder.cli as cli_mod

        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.argv", argv), patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            with self.assertRaises(SystemExit) as caught:
                cli_mod.main()
        return caught.exception.code, stdout.getvalue(), stderr.getvalue()

    def test_bare_gate_exits_deepen(self):
        code, out, _err = self._run(["knowledge-builder", "gate"])
        self.assertEqual(code, 2)
        self.assertNotIn("STOP_SUFFICIENT", out)

    def test_budget_zero_exits_pause(self):
        code, out, _err = self._run(["knowledge-builder", "gate", "--budget", "0"])
        self.assertEqual(code, 3)
        self.assertIn("PAUSE_BUDGET", out)
        self.assertNotEqual(code, 0)

    def test_removed_review_flag_is_usage_error(self):
        code, _out, err = self._run(["knowledge-builder", "gate", "--review-passed"])
        self.assertEqual(code, 1)
        self.assertIn("--review-passed", err)

    def test_exit_code_map(self):
        from knowledge_builder.cli import gate_exit_code

        self.assertEqual(gate_exit_code(TerminationState.STOP_SUFFICIENT), 0)
        self.assertEqual(gate_exit_code(TerminationState.DEEPEN), 2)
        self.assertEqual(gate_exit_code(TerminationState.PAUSE_BUDGET), 3)
        self.assertEqual(gate_exit_code(TerminationState.ABSTAIN_BLOCKED), 4)
        self.assertNotEqual(
            gate_exit_code(TerminationState.STOP_SUFFICIENT, self_reported=True),
            0,
        )

    def test_stop_reason_names_review_only_when_passed(self):
        inp = StoppingEvaluationInput(
            required_claims_total=5,
            required_claims_verified=5,
            independent_sources_count=3,
            has_execution_proof=True,
            has_counterevidence_searched=True,
            unresolved_contradictions_count=0,
            is_target_version_matched=True,
            consecutive_low_delta_rounds=3,
            last_weighted_delta=0.015,
            remaining_budget_calls=5,
            has_viable_probe_remaining=False,
            independent_review_passed=True,
        )
        res = evaluate_stopping_gate(inp)
        self.assertEqual(res.state, TerminationState.STOP_SUFFICIENT)
        self.assertIn("review passed", res.reason)

        blocked = StoppingEvaluationInput(
            required_claims_total=5,
            required_claims_verified=5,
            independent_sources_count=3,
            has_execution_proof=True,
            has_counterevidence_searched=True,
            unresolved_contradictions_count=0,
            is_target_version_matched=True,
            consecutive_low_delta_rounds=3,
            last_weighted_delta=0.01,
            remaining_budget_calls=5,
            has_viable_probe_remaining=False,
            independent_review_passed=False,
        )
        missed = evaluate_stopping_gate(blocked)
        self.assertNotIn("review passed", missed.reason)


if __name__ == "__main__":
    unittest.main()
