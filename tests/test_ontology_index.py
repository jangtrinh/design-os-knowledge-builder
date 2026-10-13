"""A4: index.json stays backwards compatible and gains ontology fields and derived properties."""

import hashlib
import json
import unittest

from tests.test_ontology_support import RootCase, run_cli


class TestIndexEnrichment(RootCase):
    def build(self):
        code, out, err = run_cli(["knowledge-builder", "index", "--root", str(self.root)])
        self.assertEqual(code, 0, out + err)
        return {e["id"]: e for e in json.loads(self.read("index.json"))}

    def test_existing_keys_unchanged(self):
        entry = self.build()["alpha"]
        self.assertEqual(entry["path"], "alpha.md")
        self.assertEqual(entry["sha256"], hashlib.sha256((self.root / "alpha.md").read_bytes()).hexdigest())

    def test_ontology_fields(self):
        entries = self.build()
        beta = entries["beta"]
        self.assertEqual(beta["object_type"], "concept")
        self.assertEqual(beta["status"], "active")
        self.assertEqual(beta["domain"], "demo")
        self.assertEqual(beta["trust_tier"], "draft")
        self.assertEqual(beta["when"], ["demo beta"])
        self.assertEqual(beta["description"], "Demo object beta.")
        self.assertIsNone(beta["superseded_by"])
        self.assertEqual(beta["links_out"], [{"link_type": "depends-on", "target_id": "alpha"}])
        self.assertEqual(beta["links_in"], [{"link_type": "compares", "source_id": "cmp"}])

    def test_links_in_is_derived_from_the_other_side(self):
        alpha = self.build()["alpha"]
        self.assertEqual(alpha["links_out"], [])
        self.assertEqual(
            alpha["links_in"],
            [{"link_type": "compares", "source_id": "cmp"}, {"link_type": "depends-on", "source_id": "beta"}],
        )

    def test_derived_properties(self):
        entry = self.build()["alpha"]
        self.assertEqual(entry["source_count"], 1)
        self.assertEqual(entry["links_in_count"], 2)
        self.assertIsInstance(entry["evidence_age_days"], int)
        self.assertGreaterEqual(entry["evidence_age_days"], 0)

    def test_status_defaults_to_experimental(self):
        self.assertEqual(self.build()["cmp"]["status"], "experimental")

    def test_legacy_root_gets_plain_fields_and_no_ontology_state(self):
        (self.root / "ontology.yaml").unlink()
        entries = self.build()
        entry = entries["alpha"]
        self.assertEqual(entry["domain"], "demo")
        self.assertEqual(entry["status"], "active")  # written in the file, not defaulted
        self.assertIsNone(entries["cmp"]["status"])

    def test_broken_schema_fails_index(self):
        self.write("ontology.yaml", "version: [oops\n")
        code, out, err = run_cli(["knowledge-builder", "index", "--root", str(self.root)])
        self.assertEqual(code, 1)
        self.assertIn("ontology.yaml", out + err)
        self.assertFalse((self.root / "index.json").exists())


if __name__ == "__main__":
    unittest.main()
