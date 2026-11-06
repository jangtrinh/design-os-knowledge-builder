"""No remaining probe and unverified required claims abstain.

DEEPEN means probing further. When nothing can be probed and required claims
are still short, the gate abstains and names the missing verified count.
A remaining probe still deepens. An exhausted budget abstains in that same
case, and pauses only when a probe is still available.
"""

import unittest

from knowledge_builder.cli import gate_exit_code
from knowledge_builder.research.stopping_gate import TerminationState, evaluate_stopping_gate
from tests.test_ontology_support import run_cli
from tests.test_stopping_gate import _passing


class TestNoProbeAbstainsWhenClaimsUnverified(unittest.TestCase):
    def test_no_probe_and_unverified_claims_abstain(self):
        res = evaluate_stopping_gate(
            _passing(required_claims_total=3, required_claims_verified=1, remaining_budget_calls=5)
        )
        self.assertEqual(res.state, TerminationState.ABSTAIN_BLOCKED)
        self.assertIn("No viable probe remains", res.reason)
        self.assertIn("unverified (1/3)", res.reason)
        self.assertNotIn("Probing further", res.reason)
        self.assertFalse(res.hard_gates_passed)
        self.assertTrue(res.saturation_passed)
        self.assertEqual(gate_exit_code(res.state), 4)

    def test_a_remaining_probe_still_deepens(self):
        res = evaluate_stopping_gate(
            _passing(
                required_claims_total=3,
                required_claims_verified=1,
                has_viable_probe_remaining=True,
            )
        )
        self.assertEqual(res.state, TerminationState.DEEPEN)
        self.assertIn("Probing further", res.reason)

    def test_exhausted_budget_without_a_probe_abstains(self):
        code, out, err = run_cli(
            ["knowledge-builder", "gate", "--budget", "0", "--required", "3", "--verified", "1"]
        )
        self.assertEqual(code, 4, out + err)
        self.assertIn("ABSTAIN_BLOCKED", out)
        self.assertIn("(1/3)", out)
        self.assertNotIn("PAUSE_BUDGET", out)


if __name__ == "__main__":
    unittest.main()
