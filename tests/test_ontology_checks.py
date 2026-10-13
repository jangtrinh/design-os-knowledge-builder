"""A2/A3: verify's ontology checks (objects, closed keys, links, lifecycle, duplicates)."""

import unittest

from knowledge_builder.ontology.checks import ontology_failures
from knowledge_builder.verify import verify_root
from tests.test_ontology_support import RootCase, run_cli


class TestChecks(RootCase):
    def failures(self):
        return ontology_failures(self.root)

    def test_clean_fixture_has_no_failures(self):
        self.assertEqual(self.failures(), [])
        code, out, err = run_cli(["knowledge-builder", "verify", str(self.root), "--claims"])
        self.assertEqual(code, 0, out + err)

    def test_error_line_format(self):
        self.replace("alpha.md", 'object_type: "concept"', 'object_type: "ghost"')
        self.assertIn("[ERROR] alpha.md object_type 'ghost' is not declared in ontology.yaml in /object_type", self.failures())

    def test_interface_name_is_not_an_object_type(self):
        self.replace("alpha.md", 'object_type: "concept"', 'object_type: "sourced-document"')
        self.assertTrue(any("is an interface" in line for line in self.failures()))

    def test_missing_object_type(self):
        self.replace("alpha.md", 'object_type: "concept"\n', "")
        self.assertIn("[ERROR] alpha.md object_type is required in /object_type", self.failures())

    def test_interface_property_and_section_required(self):
        self.replace("alpha.md", "## Purpose", "## Purposes-gone")
        self.replace("beta.md", 'description: "Demo object beta."\n', "")
        lines = self.failures()
        self.assertTrue(any(l.startswith("[ERROR] alpha.md missing section '## Purpose'") for l in lines), lines)
        self.assertTrue(any(l.startswith("[ERROR] beta.md missing property 'description'") for l in lines), lines)

    def test_enum_and_required_properties(self):
        self.replace("alpha.md", 'domain: "demo"', 'domain: "other"')
        self.assertTrue(any("domain 'other' is not one of" in l for l in self.failures()))
        self.replace("ontology.yaml", "values: [demo]}", "values: [demo], required: true}")
        self.replace("alpha.md", 'domain: "other"\n', "")
        self.assertTrue(any("alpha.md missing property 'domain'" in l for l in self.failures()))

    def test_closed_key_set_and_extra_keys(self):
        self.replace("alpha.md", 'version: "1.0.0"\n', 'version: "1.0.0"\nflavour: "x"\n')
        self.assertIn("[ERROR] alpha.md unknown key 'flavour' in /flavour", self.failures())
        self.replace("ontology.yaml", "extra_keys: []", "extra_keys: [flavour]")
        self.assertEqual(self.failures(), [])

    def test_link_checks(self):
        cases = {
            "undeclared link type": ('link_type: "depends-on"', 'link_type: "relates"', "link_type 'relates' is not declared"),
            "missing target": ('target_id: "alpha"\n', 'target_id: "nowhere"\n', "target 'nowhere' does not exist"),
            "wrong to type": ('link_type: "depends-on"\n    target_id: "alpha"', 'link_type: "compares"\n    target_id: "alpha"', "from type 'concept'"),
        }
        for label, (old, new, expect) in cases.items():
            with self.subTest(label):
                self.replace("beta.md", old, new)
                self.assertTrue(any(expect in l for l in self.failures()), (label, self.failures()))
                self.replace("beta.md", new, old)

    def test_link_to_comparison_target_with_wrong_type(self):
        self.replace("beta.md", 'target_id: "alpha"', 'target_id: "cmp"')
        self.assertTrue(any("target 'cmp' is a 'comparison'" in l for l in self.failures()))

    def test_cardinality_is_not_enforced(self):
        # compares declares many-to-many, depends-on has none; a second link of the same type is fine.
        self.replace("beta.md", 'target_id: "alpha"\n', 'target_id: "alpha"\n  - link_type: "depends-on"\n    target_id: "alpha"\n')
        self.assertEqual(self.failures(), [])

    def deprecate_alpha(self):
        self.replace("alpha.md", 'status: "active"', 'status: "deprecated"\nsuperseded_by: "beta"')

    def test_link_to_deprecated_target_names_the_replacement(self):
        self.deprecate_alpha()
        lines = self.failures()
        self.assertTrue(any("beta.md" in l and "deprecated" in l and "use 'beta'" in l for l in lines), lines)
        self.assertTrue(any("cmp.md" in l and "use 'beta'" in l for l in lines), lines)

    def test_lifecycle(self):
        self.replace("alpha.md", 'status: "active"', 'status: "retired"')
        self.assertTrue(any("status 'retired'" in l for l in self.failures()))
        self.replace("alpha.md", 'status: "retired"', 'status: "deprecated"')
        self.assertIn("[ERROR] alpha.md superseded_by is required when status is deprecated in /superseded_by", self.failures())
        self.replace("alpha.md", 'status: "deprecated"', 'status: "deprecated"\nsuperseded_by: "ghost"')
        self.assertTrue(any("superseded_by 'ghost' does not resolve" in l for l in self.failures()))

    def test_status_defaults_to_experimental(self):
        self.replace("alpha.md", 'status: "active"\n', "")
        self.assertEqual(self.failures(), [])

    def test_duplicate_id_across_directories(self):
        sub = self.root / "sub"
        sub.mkdir()
        (sub / "alpha.md").write_text(self.read("alpha.md"), encoding="utf-8")
        lines = self.failures()
        self.assertEqual(sum("duplicate id 'alpha'" in l for l in lines), 2, lines)

    def test_verify_root_includes_ontology_failures(self):
        self.replace("alpha.md", 'object_type: "concept"', 'object_type: "ghost"')
        _f, _a, failures, _e = verify_root(self.root)
        self.assertTrue(any(l.startswith("[ERROR] alpha.md object_type 'ghost'") for l in failures))

    def test_bad_ontology_yaml_is_one_failure(self):
        self.write("ontology.yaml", "version: [oops\n")
        lines = self.failures()
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("[ERROR] ontology.yaml "))

    def test_legacy_root_warns_and_adds_no_failures(self):
        (self.root / "ontology.yaml").unlink()
        import io
        from unittest.mock import patch
        err = io.StringIO()
        with patch("sys.stderr", err):
            self.assertEqual(self.failures(), [])
        self.assertIn("legacy", err.getvalue())


if __name__ == "__main__":
    unittest.main()
