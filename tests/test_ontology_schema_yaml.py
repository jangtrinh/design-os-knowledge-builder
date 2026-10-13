"""ontology.yaml subset parser: block + flow forms, strict failures with a line number."""

import unittest

from knowledge_builder.ontology.schema_yaml import SchemaSyntaxError, parse_schema_yaml


class TestSchemaYaml(unittest.TestCase):
    def test_block_map_list_and_flow_forms(self):
        text = (
            'version: "1"\n'
            "# comment\n"
            "interfaces:\n"
            "  sourced-document:\n"
            "    properties: [title, description]\n"
            '    sections: ["## Purpose", "## Core"]\n'
            "object_types:\n"
            "  concept:\n"
            "    implements: [sourced-document]\n"
            "    properties:\n"
            "      - {name: domain, type: enum, values: [a, b]}\n"
            "link_types:\n"
            "  - {link_type: compares, from: comparison, to: concept}\n"
            "  - link_type: depends-on\n"
            "    from: concept\n"
            "    to: concept\n"
            "extra_keys: []\n"
        )
        data = parse_schema_yaml(text)
        self.assertEqual(data["version"], "1")
        self.assertEqual(data["interfaces"]["sourced-document"]["sections"], ["## Purpose", "## Core"])
        self.assertEqual(
            data["object_types"]["concept"]["properties"][0],
            {"name": "domain", "type": "enum", "values": ["a", "b"]},
        )
        self.assertEqual(data["link_types"][1], {"link_type": "depends-on", "from": "concept", "to": "concept"})
        self.assertEqual(data["extra_keys"], [])

    def test_nested_flow_map_in_flow_map(self):
        data = parse_schema_yaml("a:\n  - {set: {object: target, key: status, value: \"$x\"}}\n")
        self.assertEqual(data["a"][0], {"set": {"object": "target", "key": "status", "value": "$x"}})

    def test_failures_name_the_line(self):
        for bad in ("a: [x,\n", "a: {k v}\n", "a: 1\na: 2\n", "a:\n    b: 1\n  c: 2\n", "a: 'open\n"):
            with self.subTest(bad=bad), self.assertRaises(SchemaSyntaxError) as caught:
                parse_schema_yaml(bad)
            self.assertIn("line", str(caught.exception))

    def test_every_list_item_needs_a_dash_space_marker(self):
        for bad in ("extra_keys:\n  - a\n  -forbidden\n", "extra_keys:\n  -a\n"):
            with self.subTest(bad), self.assertRaises(SchemaSyntaxError):
                parse_schema_yaml(bad)

    def test_colon_space_inside_a_plain_flow_scalar_is_a_missing_comma(self):
        with self.assertRaises(SchemaSyntaxError) as caught:
            parse_schema_yaml("properties: [{name: rank type: integer}]\n")
        self.assertIn("line 1", str(caught.exception))
        self.assertEqual(parse_schema_yaml("u: [http://x.y/z]\n"), {"u": ["http://x.y/z"]})


if __name__ == "__main__":
    unittest.main()
