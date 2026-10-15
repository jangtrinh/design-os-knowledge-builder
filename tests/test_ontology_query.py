"""A5: query is a read-only object-set filter over a fresh index.json."""

import json
import unittest

from tests.test_ontology_support import RootCase, run_cli


class TestQuery(RootCase):
    def setUp(self):
        super().setUp()
        code, out, err = run_cli(["knowledge-builder", "index", "--root", str(self.root)])
        self.assertEqual(code, 0, out + err)

    def query(self, *args):
        code, out, err = run_cli(["knowledge-builder", "query", "--root", str(self.root), *args])
        return code, (json.loads(out) if code == 0 else None), out + err

    def ids(self, *args):
        code, rows, text = self.query(*args)
        self.assertEqual(code, 0, text)
        return [row["id"] for row in rows]

    def test_filters(self):
        self.assertEqual(self.ids("--object-type", "concept"), ["alpha", "beta"])
        self.assertEqual(self.ids("--object-type", "concept", "--status", "active"), ["alpha", "beta"])
        self.assertEqual(self.ids("--status", "experimental"), ["cmp"])
        self.assertEqual(self.ids("--implements", "sourced-document"), ["alpha", "beta", "cmp"])
        self.assertEqual(self.ids("--where", "domain=demo", "--where", "trust_tier=draft"), ["alpha", "beta", "cmp"])
        self.assertEqual(self.ids("--where", "when=demo beta"), ["beta"])

    def test_linked_to_covers_both_sides_and_link_type(self):
        self.assertEqual(self.ids("--linked-to", "alpha"), ["beta", "cmp"])
        self.assertEqual(self.ids("--linked-to", "alpha", "--link-type", "compares"), ["cmp"])
        self.assertEqual(self.ids("--linked-to", "cmp"), ["alpha", "beta"])
        self.assertEqual(self.query("--linked-to", "nobody")[0], 1)  # an unknown id is an error, not []

    def test_fields_projection(self):
        code, rows, text = self.query("--object-type", "comparison", "--fields", "id,status,links_out")
        self.assertEqual(code, 0, text)
        self.assertEqual(list(rows[0]), ["id", "status", "links_out"])

    def test_unknown_field_and_bad_where_fail(self):
        self.assertEqual(self.query("--fields", "nope")[0], 1)
        self.assertEqual(self.query("--where", "nokey")[0], 1)

    def test_stale_index_says_run_index(self):
        self.replace("alpha.md", "Demo.", "Edited.")
        code, _rows, text = self.query("--object-type", "concept")
        self.assertEqual(code, 1)
        self.assertIn("run index", text)
        self.assertIn("alpha.md", text)

    def test_new_and_removed_files_are_stale(self):
        (self.root / "gamma.md").write_text(self.read("alpha.md").replace('"alpha"', '"gamma"'), encoding="utf-8")
        self.assertIn("gamma.md", self.query()[2])
        (self.root / "gamma.md").unlink()
        (self.root / "beta.md").unlink()
        self.assertIn("beta.md", self.query()[2])

    def test_stale_list_is_capped(self):
        for number in range(8):
            (self.root / f"extra-{number}.md").write_text("x", encoding="utf-8")
        text = self.query()[2]
        self.assertIn("and 3 more", text)

    def test_missing_index_says_run_index(self):
        (self.root / "index.json").unlink()
        code, _rows, text = self.query()
        self.assertEqual(code, 1)
        self.assertIn("run index", text)

    def test_query_writes_nothing(self):
        before = {p.name: p.read_bytes() for p in self.root.glob("*") if p.is_file()}
        self.query("--object-type", "concept")
        after = {p.name: p.read_bytes() for p in self.root.glob("*") if p.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
