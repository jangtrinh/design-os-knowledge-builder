"""A hand-edited index is stale, and a rewritten frozen capture is stale too.

query, pack check, and validate load one fresh index. Recomputed fields must
match the stored entry. evidence_age_days moves with the clock, so it is
filled in when the index is read and a stored age alone is not staleness.
"""

import json
import unittest

from tests.test_ontology_support import RootCase, run_cli


class TestHandEditedIndexIsStale(RootCase):
    def _index(self):
        code, out, err = run_cli(["knowledge-builder", "index", "--root", str(self.root)])
        self.assertEqual(code, 0, out + err)

    def _entries(self):
        return json.loads(self.read("index.json"))

    def _save(self, entries):
        self.write("index.json", json.dumps(entries))

    def test_edited_trust_tier_and_links_out_are_stale(self):
        self._index()
        entries = self._entries()
        for entry in entries:
            if entry["id"] == "beta":
                entry["trust_tier"] = "verified"
                entry["links_out"] = []
        self._save(entries)

        code, out, err = run_cli(["knowledge-builder", "pack", "check", "--root", str(self.root)])
        text = out + err
        self.assertIn("index: not fresh", text)
        self.assertIn("trust_tier", text)
        self.assertIn("links_out", text)
        self.assertIn("beta.md", text)

        code, out, err = run_cli(
            ["knowledge-builder", "query", "--root", str(self.root), "--fields", "id,trust_tier,links_out"]
        )
        self.assertEqual(code, 1, out + err)
        self.assertIn("trust_tier", out + err)
        self.assertIn("links_out", out + err)
        self.assertIn("beta.md", out + err)
        self.assertIn("run index", out + err)

    def test_overwritten_frozen_source_is_stale_for_source_count(self):
        self._index()
        frozen = self.root / "_evidence" / "run-1" / "sources" / "source.txt"
        frozen.write_text("replaced capture\n", encoding="utf-8")

        code, out, err = run_cli(["knowledge-builder", "verify", "--claims", str(self.root)])
        self.assertNotEqual(code, 0, out + err)

        code, out, err = run_cli(
            ["knowledge-builder", "query", "--root", str(self.root), "--fields", "id,source_count"]
        )
        self.assertEqual(code, 1, out + err)
        self.assertIn("source_count", out + err)
        self.assertIn("alpha.md", out + err)
        self.assertIn("frozen capture is missing or its sha256 differs", out + err)

    def test_deleted_frozen_source_is_stale(self):
        self._index()
        frozen = self.root / "_evidence" / "run-1" / "sources" / "source.txt"
        frozen.unlink()

        code, out, err = run_cli(["knowledge-builder", "verify", "--claims", str(self.root)])
        self.assertNotEqual(code, 0, out + err)

        code, out, err = run_cli(
            ["knowledge-builder", "query", "--root", str(self.root), "--fields", "id,source_count"]
        )
        self.assertEqual(code, 1, out + err)
        self.assertIn("alpha.md", out + err)
        self.assertIn("frozen capture", out + err)

    def test_stored_evidence_age_is_replaced_at_read_time(self):
        self._index()
        entries = self._entries()
        stored = {entry["id"]: entry["evidence_age_days"] for entry in entries}
        for entry in entries:
            entry["evidence_age_days"] = 99999
        self._save(entries)

        code, out, err = run_cli(
            ["knowledge-builder", "query", "--root", str(self.root), "--fields", "id,evidence_age_days"]
        )
        self.assertEqual(code, 0, out + err)
        for row in json.loads(out):
            self.assertNotEqual(row["evidence_age_days"], 99999)
            self.assertEqual(row["evidence_age_days"], stored[row["id"]])


if __name__ == "__main__":
    unittest.main()
