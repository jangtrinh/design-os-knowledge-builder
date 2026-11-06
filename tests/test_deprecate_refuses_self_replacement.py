"""deprecate refuses a replacement that is the target itself.

The refusal happens before any edit. The target file stays active, the action
log stays empty, and the rejection trace records why.
"""

import json

from knowledge_builder.ontology.actions import ActionError, run_action
from tests.test_ontology_actions import ActionCase, snapshot


class TestDeprecateRefusesSelfReplacement(ActionCase):
    def test_target_cannot_replace_itself(self):
        before = snapshot(self.root)
        with self.assertRaises(ActionError) as caught:
            run_action(self.root, "deprecate", {"target": "beta", "replacement": "beta"})
        message = str(caught.exception)
        self.assertIn("replacement must differ", message)
        self.assertIn("beta", message)
        self.assertNotIn("verify failed", message)
        self.assertEqual(snapshot(self.root), before)
        self.assertIn('status: "active"', self.read("beta.md"))
        self.assertNotIn("superseded_by", self.read("beta.md"))
        rejected = (self.root / "_actions" / "rejected.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(rejected), 1)
        record = json.loads(rejected[0])
        self.assertEqual(record["action"], "deprecate")
        self.assertEqual(record["params"], {"target": "beta", "replacement": "beta"})
        self.assertIn("replacement must differ", record["reason"])
        self.assertFalse((self.root / "_actions" / "actions.jsonl").exists())


if __name__ == "__main__":
    import unittest
    unittest.main()
