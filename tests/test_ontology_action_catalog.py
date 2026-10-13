"""Default action catalog: trust promotion needs stopped runs; declared actions merge with the defaults."""

import unittest

from knowledge_builder.ontology.actions import ActionError, run_action
from tests.test_ontology_actions import ActionCase, snapshot
from tests.test_ontology_support import make_stop_run


class TestPromote(ActionCase):
    def test_promote_trust_tier_needs_verified_claims_and_a_stopped_run(self):
        params = {"target": "alpha", "tier": "verified"}
        with self.assertRaises(ActionError) as caught:
            run_action(self.root, "promote-trust-tier", params)  # run-1 has no state.json
        self.assertIn("runs-stop-sufficient", str(caught.exception))
        make_stop_run(self.root)
        run_action(self.root, "promote-trust-tier", params)
        self.assertEqual(self.index()["alpha"]["trust_tier"], "verified")
        self.replace("beta.md", 'quote="Alpha facts live here."', 'quote="Not in the source."')
        before = snapshot(self.root)
        with self.assertRaises(ActionError) as caught:
            run_action(self.root, "promote-trust-tier", {"target": "beta", "tier": "verified"})
        self.assertIn("claims-verified", str(caught.exception))
        self.assertEqual(snapshot(self.root), before)


class TestMerge(ActionCase):
    def test_declared_action_types_merge_with_the_defaults_and_override_by_name(self):
        self.write("ontology.yaml", self.read("ontology.yaml") + (
            "action_types:\n"
            "  retire:\n"
            "    parameters: {target: {type: object_id}}\n"
            "    criteria: [{function: status-is, args: [target, active]}]\n"
            "    edits:\n"
            "      - {set: {object: target, key: status, value: experimental}}\n"
        ))
        run_action(self.root, "retire", {"target": "beta"})
        self.assertIn('status: "experimental"', self.read("beta.md"))
        run_action(self.root, "add-link", {"source": "cmp", "link_type": "compares", "target": "beta"})  # default kept
        self.write("ontology.yaml", self.read("ontology.yaml") + (
            "  deprecate:\n    parameters: {target: {type: object_id}}\n"
            "    edits: [{set: {object: target, key: status, value: active}}]\n"
        ))
        run_action(self.root, "deprecate", {"target": "beta"})  # root's own definition wins
        self.assertIn('status: "active"', self.read("beta.md"))


if __name__ == "__main__":
    unittest.main()
