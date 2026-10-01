"""Test Stopping Gate logic across the 11 core scenarios formulated by Codex Native Astra."""

import unittest
from knowledge_builder.research.stopping_gate import evaluate_stopping_gate, StoppingEvaluationInput, TerminationState


class TestStoppingGateScenarios(unittest.TestCase):

    def test_scenario_1_sufficient_evidence(self):
        """Scenario 1: All hard gates pass + saturation reached -> STOP_SUFFICIENT."""
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
        self.assertTrue(res.hard_gates_passed)
        self.assertTrue(res.saturation_passed)
        self.assertIsNotNone(res.certificate)

    def test_scenario_2_low_delta_but_missing_critical_claims(self):
        """Scenario 2: Delta is low but critical claims are still missing -> DEEPEN."""
        inp = StoppingEvaluationInput(
            required_claims_total=5,
            required_claims_verified=3,  # Missing 2
            independent_sources_count=3,
            has_execution_proof=True,
            has_counterevidence_searched=True,
            unresolved_contradictions_count=0,
            is_target_version_matched=True,
            consecutive_low_delta_rounds=3,
            last_weighted_delta=0.01,
            remaining_budget_calls=5,
            has_viable_probe_remaining=True,
        )
        res = evaluate_stopping_gate(inp)
        self.assertEqual(res.state, TerminationState.DEEPEN)
        self.assertFalse(res.hard_gates_passed)

    def test_scenario_3_many_urls_same_origin(self):
        """Scenario 3: Single origin (1 independent source despite many URLs) -> DEEPEN."""
        inp = StoppingEvaluationInput(
            required_claims_total=5,
            required_claims_verified=5,
            independent_sources_count=1,  # Only 1 true independent source
            has_execution_proof=True,
            has_counterevidence_searched=True,
            unresolved_contradictions_count=0,
            is_target_version_matched=True,
            consecutive_low_delta_rounds=3,
            last_weighted_delta=0.01,
            remaining_budget_calls=5,
            has_viable_probe_remaining=True,
        )
        res = evaluate_stopping_gate(inp)
        self.assertEqual(res.state, TerminationState.DEEPEN)

    def test_scenario_4_marketing_no_execution_proof(self):
        """Scenario 4: Documentation claims without runnable code proof -> DEEPEN."""
        inp = StoppingEvaluationInput(
            required_claims_total=5,
            required_claims_verified=5,
            independent_sources_count=3,
            has_execution_proof=False,  # No execution test
            has_counterevidence_searched=True,
            unresolved_contradictions_count=0,
            is_target_version_matched=True,
            consecutive_low_delta_rounds=3,
            last_weighted_delta=0.01,
            remaining_budget_calls=5,
            has_viable_probe_remaining=True,
        )
        res = evaluate_stopping_gate(inp)
        self.assertEqual(res.state, TerminationState.DEEPEN)

    def test_scenario_5_unresolved_contradictions(self):
        """Scenario 5: Active contradictory claims between sources -> DEEPEN."""
        inp = StoppingEvaluationInput(
            required_claims_total=5,
            required_claims_verified=5,
            independent_sources_count=3,
            has_execution_proof=True,
            has_counterevidence_searched=True,
            unresolved_contradictions_count=2,  # 2 active contradictions
            is_target_version_matched=True,
            consecutive_low_delta_rounds=3,
            last_weighted_delta=0.01,
            remaining_budget_calls=5,
            has_viable_probe_remaining=True,
        )
        res = evaluate_stopping_gate(inp)
        self.assertEqual(res.state, TerminationState.DEEPEN)

    def test_scenario_6_version_drift(self):
        """Scenario 6: Version mismatch -> DEEPEN."""
        inp = StoppingEvaluationInput(
            required_claims_total=5,
            required_claims_verified=5,
            independent_sources_count=3,
            has_execution_proof=True,
            has_counterevidence_searched=True,
            unresolved_contradictions_count=0,
            is_target_version_matched=False,  # Version drift
            consecutive_low_delta_rounds=3,
            last_weighted_delta=0.01,
            remaining_budget_calls=5,
            has_viable_probe_remaining=True,
        )
        res = evaluate_stopping_gate(inp)
        self.assertEqual(res.state, TerminationState.DEEPEN)

    def test_scenario_7_missing_counterevidence_search(self):
        """Scenario 7: No failure/anti-pattern search conducted -> DEEPEN."""
        inp = StoppingEvaluationInput(
            required_claims_total=5,
            required_claims_verified=5,
            independent_sources_count=3,
            has_execution_proof=True,
            has_counterevidence_searched=False,  # Not searched
            unresolved_contradictions_count=0,
            is_target_version_matched=True,
            consecutive_low_delta_rounds=3,
            last_weighted_delta=0.01,
            remaining_budget_calls=5,
            has_viable_probe_remaining=True,
        )
        res = evaluate_stopping_gate(inp)
        self.assertEqual(res.state, TerminationState.DEEPEN)

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


if __name__ == "__main__":
    unittest.main()
