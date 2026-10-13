"""A7: built-in function registry only; nothing is imported or executed from the root."""

import unittest

from knowledge_builder.ontology.functions import FUNCTIONS, Context
from knowledge_builder.ontology.objects import load_graph
from knowledge_builder.ontology.schema import OntologyError, load_ontology
from tests.test_ontology_support import RootCase


class TestFunctions(RootCase):
    def ctx(self):
        return Context(self.root, load_graph(self.root))

    def test_registry_is_exactly_the_designed_set(self):
        self.assertEqual(
            sorted(FUNCTIONS),
            ["claims-verified", "evidence-age-days", "has-link", "links-in-count", "object-exists", "source-count", "status-is"],
        )

    def test_predicates(self):
        ctx = self.ctx()
        self.assertTrue(FUNCTIONS["object-exists"](ctx, "alpha"))
        self.assertFalse(FUNCTIONS["object-exists"](ctx, "nope"))
        self.assertTrue(FUNCTIONS["status-is"](ctx, "alpha", "active"))
        self.assertTrue(FUNCTIONS["status-is"](ctx, "cmp", "experimental"))
        self.assertFalse(FUNCTIONS["status-is"](ctx, "nope", "active"))
        self.assertTrue(FUNCTIONS["has-link"](ctx, "beta", "depends-on", "alpha"))
        self.assertFalse(FUNCTIONS["has-link"](ctx, "alpha", "depends-on", "beta"))

    def test_derived_values(self):
        ctx = self.ctx()
        self.assertEqual(FUNCTIONS["source-count"](ctx, "alpha"), 1)
        self.assertEqual(FUNCTIONS["links-in-count"](ctx, "alpha"), 2)
        self.assertEqual(FUNCTIONS["links-in-count"](ctx, "cmp"), 0)
        self.assertGreaterEqual(FUNCTIONS["evidence-age-days"](ctx, "alpha"), 0)

    def test_claims_verified_follows_the_quote_check(self):
        self.assertTrue(FUNCTIONS["claims-verified"](self.ctx(), "alpha"))
        self.replace("alpha.md", 'quote="Alpha facts live here."', 'quote="Not in the source."')
        self.assertFalse(FUNCTIONS["claims-verified"](self.ctx(), "alpha"))
        self.assertTrue(FUNCTIONS["claims-verified"](self.ctx(), "beta"))

    def test_root_code_is_never_loaded(self):
        marker = self.root / "executed.txt"
        (self.root / "functions.py").write_text(f"open({str(marker)!r}, 'w').write('x')\n", encoding="utf-8")
        (self.root / "sneaky.py").write_text(f"open({str(marker)!r}, 'w').write('x')\n", encoding="utf-8")
        self.write("ontology.yaml", self.read("ontology.yaml") + "action_types:\n  x:\n    criteria: [{function: sneaky, args: [a]}]\n")
        with self.assertRaises(OntologyError):
            load_ontology(self.root)
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
