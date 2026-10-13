"""One Markdown discovery rule for verify and ontology checks; query refuses an index it cannot trust."""

import json
import os
import unittest

from knowledge_builder.ontology.checks import ontology_failures
from knowledge_builder.verify import verify_root
from tests.test_ontology_support import RootCase, run_cli


class TestUppercaseExtension(RootCase):
    def test_upper_case_md_gets_the_same_ontology_checks(self):
        sub = self.root / "sub"
        sub.mkdir()
        bad = self.read("alpha.md").replace('object_type: "concept"', 'object_type: "bogus-type"')
        (sub / "alpha.MD").write_text(bad, encoding="utf-8")
        lines = ontology_failures(self.root)
        self.assertTrue(any("sub/alpha.MD" in l and "bogus-type" in l for l in lines), lines)
        self.assertTrue(any("duplicate id 'alpha'" in l and "sub/alpha.MD" in l for l in lines), lines)
        _f, _a, failures, _e = verify_root(self.root)
        self.assertTrue(any("bogus-type" in l for l in failures))


class TestLinkToUntypedTarget(RootCase):
    def test_target_without_object_type_fails_the_to_type_check(self):
        self.replace("alpha.md", 'object_type: "concept"\n', "")
        lines = ontology_failures(self.root)
        self.assertTrue(any("beta.md" in l and "target 'alpha'" in l and "needs 'concept'" in l for l in lines), lines)


class FreshCase(RootCase):
    def setUp(self):
        super().setUp()
        code, out, err = run_cli(["knowledge-builder", "index", "--root", str(self.root)])
        self.assertEqual(code, 0, out + err)

    def query(self):
        return run_cli(["knowledge-builder", "query", "--root", str(self.root)])


class TestDiscoveryErrors(FreshCase):
    def test_escaping_symlink_makes_the_index_untrusted(self):
        outside = self.root.parent / "outside-note.md"
        outside.write_text("x", encoding="utf-8")
        os.symlink(outside, self.root / "evil.md")
        code, _out, err = self.query()
        self.assertEqual(code, 1)
        self.assertIn("evil.md", err)
        self.assertIn("run index", err)


class TestOntologyStateInFreshness(FreshCase):
    def test_removing_or_changing_ontology_yaml_makes_the_index_stale(self):
        original = self.read("ontology.yaml")
        self.assertEqual(self.query()[0], 0)
        self.write("ontology.yaml", original + "\n# edited\n")
        code, _out, err = self.query()
        self.assertEqual(code, 1)
        self.assertIn("ontology.yaml", err)
        (self.root / "ontology.yaml").unlink()
        code, _out, err = self.query()
        self.assertEqual((code, "ontology.yaml" in err), (1, True))

    def test_adding_ontology_yaml_to_a_legacy_index_is_stale(self):
        saved = self.read("ontology.yaml")
        (self.root / "ontology.yaml").unlink()
        run_cli(["knowledge-builder", "index", "--root", str(self.root)])
        self.assertEqual(self.query()[0], 0)
        self.write("ontology.yaml", saved)
        code, _out, err = self.query()
        self.assertEqual((code, "ontology.yaml" in err), (1, True))

    def test_index_records_the_schema_hash(self):
        entries = json.loads(self.read("index.json"))
        self.assertTrue(all(len(e["ontology_sha256"]) == 64 for e in entries))


if __name__ == "__main__":
    unittest.main()
