"""A1: ontology.yaml loader."""

import unittest

from knowledge_builder.ontology.schema import OntologyError, load_ontology
from tests.test_ontology_support import RootCase


class TestLoader(RootCase):
    def test_fixture_loads_and_resolves(self):
        onto = load_ontology(self.root)
        self.assertEqual(sorted(onto.object_types), ["comparison", "concept"])
        self.assertEqual(onto.implementing("sourced-document"), ["comparison", "concept"])
        self.assertEqual(onto.link_types["compares"]["to"], "concept")
        self.assertIsNone(onto.action_types)  # defaults ship

    def test_missing_file_is_legacy_mode(self):
        (self.root / "ontology.yaml").unlink()
        self.assertIsNone(load_ontology(self.root))

    def test_bool_and_int_are_coerced(self):
        self.replace("ontology.yaml", "{name: domain, type: enum, values: [demo]}",
                     "{name: domain, type: enum, values: [demo], required: true}")
        self.replace("ontology.yaml", "comparison:\n    implements: [sourced-document]\n",
                     "comparison:\n    implements: [sourced-document]\n    properties:\n      - {name: rank, type: integer, min: 1, max: 9}\n")
        onto = load_ontology(self.root)
        self.assertIs(onto.declared_properties("concept")["domain"]["required"], True)
        rank = onto.declared_properties("comparison")["rank"]
        self.assertEqual((rank["min"], rank["max"]), (1, 9))

    def test_bad_schemas_are_load_errors(self):
        cases = {
            "undeclared interface": ("implements: [sourced-document]\n    properties:", "implements: [nope]\n    properties:"),
            "link target type": ("to: concept, cardinality", "to: ghost, cardinality"),
            "uppercase name": ("  concept:\n", "  Concept:\n"),
            "two parents": ("implements: [sourced-document]\n    properties:", "implements: [sourced-document, sourced-document]\n    properties:"),
        }
        for label, (old, new) in cases.items():
            with self.subTest(label):
                self.replace("ontology.yaml", old, new)
                with self.assertRaises(OntologyError):
                    load_ontology(self.root)
                self.replace("ontology.yaml", new, old)

    def test_interface_cannot_be_an_object_type(self):
        self.replace("ontology.yaml", "object_types:\n", "object_types:\n  sourced-document:\n    properties: []\n")
        with self.assertRaises(OntologyError):
            load_ontology(self.root)

    def test_unknown_function_and_verb_are_load_errors(self):
        base = open(self.root / "ontology.yaml").read()
        bad_fn = base + "action_types:\n  x:\n    criteria: [{function: shell-out, args: [a]}]\n"
        self.write("ontology.yaml", bad_fn)
        with self.assertRaises(OntologyError) as caught:
            load_ontology(self.root)
        self.assertIn("shell-out", str(caught.exception))
        self.write("ontology.yaml", base + "action_types:\n  x:\n    edits: [{delete: {object: a}}]\n")
        with self.assertRaises(OntologyError):
            load_ontology(self.root)

    def test_syntax_error_names_the_line(self):
        self.write("ontology.yaml", 'version: "1"\nobject_types: [x\n')
        with self.assertRaises(OntologyError) as caught:
            load_ontology(self.root)
        self.assertIn("line 2", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
