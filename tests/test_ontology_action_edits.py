"""Text-level frontmatter edits: only the touched lines change, everything else stays byte-identical."""

import unittest

from knowledge_builder.frontmatter import parse_frontmatter
from knowledge_builder.ontology.action_edits import EditError, add_link, remove_link, set_key

DOC = '''---
id: "a"
title: "A"
status: "active"
when:
  - "x"
---

body: keep
'''


class TestSetKey(unittest.TestCase):
    def test_replaces_only_that_line(self):
        out = set_key(DOC, "status", "deprecated")
        self.assertEqual(out, DOC.replace('status: "active"', 'status: "deprecated"'))

    def test_appends_before_closing_fence(self):
        out = set_key(DOC, "superseded_by", "b")
        self.assertEqual(parse_frontmatter(out)["superseded_by"], "b")
        self.assertEqual(out.replace('superseded_by: "b"\n', ""), DOC)

    def test_quotes_and_escapes(self):
        out = set_key(DOC, "title", 'He said "hi": ok')
        self.assertEqual(parse_frontmatter(out)["title"], 'He said "hi": ok')

    def test_refuses_structured_and_identity_keys(self):
        for key in ("when", "id", "link_types", "source_attribution"):
            with self.subTest(key), self.assertRaises(EditError):
                set_key(DOC, key, "x")

    def test_no_frontmatter_is_an_error(self):
        with self.assertRaises(EditError):
            set_key("no fence\n", "status", "x")


class TestLinks(unittest.TestCase):
    def test_add_creates_block_then_appends(self):
        one = add_link(DOC, "depends-on", "b")
        self.assertEqual(parse_frontmatter(one)["link_types"], [{"link_type": "depends-on", "target_id": "b"}])
        two = add_link(one, "compares", "c")
        self.assertEqual(
            parse_frontmatter(two)["link_types"],
            [{"link_type": "depends-on", "target_id": "b"}, {"link_type": "compares", "target_id": "c"}],
        )
        self.assertTrue(two.endswith("---\n\nbody: keep\n"))

    def test_add_duplicate_is_an_error(self):
        with self.assertRaises(EditError):
            add_link(add_link(DOC, "depends-on", "b"), "depends-on", "b")

    def test_add_into_empty_flow_list(self):
        out = add_link(DOC.replace('status: "active"', "link_types: []"), "depends-on", "b")
        self.assertEqual(parse_frontmatter(out)["link_types"], [{"link_type": "depends-on", "target_id": "b"}])

    def test_add_after_block_that_is_not_last(self):
        text = add_link(DOC, "depends-on", "b").replace("when:", "version: \"1\"\nwhen:", 1)
        out = add_link(text, "compares", "c")
        self.assertEqual(len(parse_frontmatter(out)["link_types"]), 2)
        self.assertEqual(parse_frontmatter(out)["version"], "1")

    def test_remove_one_then_last_drops_the_key(self):
        both = add_link(add_link(DOC, "depends-on", "b"), "compares", "c")
        one = remove_link(both, "depends-on", "b")
        self.assertEqual(parse_frontmatter(one)["link_types"], [{"link_type": "compares", "target_id": "c"}])
        self.assertEqual(remove_link(one, "compares", "c"), DOC)

    def test_remove_missing_is_an_error(self):
        with self.assertRaises(EditError):
            remove_link(DOC, "depends-on", "b")


if __name__ == "__main__":
    unittest.main()
