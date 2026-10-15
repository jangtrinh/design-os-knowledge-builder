"""create-object for typed objects: declared folder, declared properties, repeatable fields, interface-less types."""

import hashlib
import unittest

from knowledge_builder.frontmatter import parse_frontmatter
from knowledge_builder.ontology.actions import ActionError, run_action
from tests.pack_support import PackCase, freeze, scaffold_root
from tests.test_ontology_support import run_cli

TYPES = """  architecture:
    folder: entities
    properties:
      - {name: family, type: enum, values: [semantic-web, property-graph], required: true}
      - {name: tier, type: integer, min: 1, max: 5}
      - {name: curated, type: boolean}
"""


def tree(root):
    refusal_trace = {"_actions", "_actions/rejected.jsonl"}  # the only entries a refused action may add
    return sorted(rel for rel in (p.relative_to(root).as_posix() for p in root.rglob("*") if "_evidence" not in p.parts) if rel not in refusal_trace)


class TypedCase(PackCase):
    def setUp(self):
        super().setUp()
        scaffold_root(self.root)
        self.replace("ontology.yaml", "link_types:\n", TYPES + "link_types:\n")
        self.uri_a, self.sha_a = freeze(self.root, "src-a", "Alpha body.")
        self.uri_b, self.sha_b = freeze(self.root, "src-b", "Beta body.")

    def create(self, **params):
        return run_action(self.root, "create-object", params)

    def entity(self, **extra):
        return dict({"id": "foundry", "object_type": "architecture", "title": "Foundry", "family": "semantic-web"}, **extra)

    def doc(self, **extra):
        return dict({"id": "doc-x", "object_type": "concept", "title": "T", "domain": "demo", "description": "D",
                     "when": "w", "source": self.uri_a}, **extra)


class TestFolder(TypedCase):
    def test_object_is_written_into_its_types_folder_and_verifies(self):
        record = self.create(**self.entity())
        self.assertEqual(record["files"], ["entities/foundry.md"])
        self.assertEqual(self.verify(claims=False), [])
        self.assertEqual(self.verify(claims=True), [])

    def test_a_type_without_a_folder_stays_at_the_root(self):
        self.assertEqual(self.create(**self.doc())["files"], ["doc-x.md"])

    def test_a_failed_action_leaves_no_new_folder_behind(self):
        from unittest.mock import patch

        before = tree(self.root)
        with patch("knowledge_builder.ontology.actions.rebuild_index", side_effect=ActionError("boom")):
            with self.assertRaises(ActionError):
                self.create(**self.entity())
        self.assertEqual(tree(self.root), before)
        self.assertFalse((self.root / "entities").exists())


class TestDeclaredProperties(TypedCase):
    def test_declared_typed_values_are_written(self):
        self.create(**self.entity(tier="3", curated="true"))
        data = parse_frontmatter(self.read("entities/foundry.md"))
        self.assertEqual((data["family"], data["tier"], data["curated"]), ("semantic-web", "3", "true"))
        self.assertEqual(self.verify(claims=False), [])

    def test_values_that_break_the_schema_are_refused_and_change_nothing(self):
        before = tree(self.root)
        for params, needle in [
            (self.entity(family="graph"), "family"),
            (self.entity(tier="9"), "tier"),
            (self.entity(tier="three"), "tier"),
            (self.entity(curated="yes"), "curated"),
        ]:
            with self.subTest(params=params):
                with self.assertRaises(ActionError) as caught:
                    self.create(**params)
                self.assertIn(needle, str(caught.exception))
        self.assertEqual(tree(self.root), before)

    def test_an_undeclared_name_is_refused_and_the_declared_ones_are_listed(self):
        with self.assertRaises(ActionError) as caught:
            self.create(**self.entity(colour="red"))
        message = str(caught.exception)
        self.assertIn("unknown parameter 'colour'", message)
        for name in ("family", "tier", "curated", "title", "id", "object_type"):
            self.assertIn(name, message)

    def test_a_required_declared_property_must_be_given(self):
        params = self.entity()
        del params["family"]
        with self.assertRaises(ActionError) as caught:
            self.create(**params)
        self.assertIn("missing parameter 'family'", str(caught.exception))

    def test_a_document_type_keeps_its_fixed_parameters(self):
        with self.assertRaises(ActionError) as caught:
            self.create(**self.doc(family="semantic-web"))
        self.assertIn("unknown parameter 'family'", str(caught.exception))
        params = self.doc()
        del params["when"]
        with self.assertRaises(ActionError):
            self.create(**params)


class TestRepeatable(TypedCase):
    def test_when_and_source_repeat_with_one_attribution_entry_each(self):
        self.create(**self.doc(when=["first trigger", "second trigger"], source=[self.uri_a, self.uri_b]))
        data = parse_frontmatter(self.read("doc-x.md"))
        self.assertEqual(data["when"], ["first trigger", "second trigger"])
        self.assertEqual(data["source_attribution"], [{"uri": self.uri_a, "sha256": self.sha_a}, {"uri": self.uri_b, "sha256": self.sha_b}])
        self.assertEqual(self.verify(claims=False), [])

    def test_repeated_param_flags_on_the_command_line(self):
        code, out, err = run_cli([
            "knowledge-builder", "action", "create-object", "--root", str(self.root), "--param", "id=doc-x", "--param", "object_type=concept",
            "--param", "title=T", "--param", "domain=demo", "--param", "description=D", "--param", "when=a", "--param", "when=b",
            "--param", f"source={self.uri_a}", "--param", f"source={self.uri_b}",
        ])
        self.assertEqual(code, 0, out + err)
        self.assertEqual(parse_frontmatter(self.read("doc-x.md"))["when"], ["a", "b"])

    def test_a_single_value_is_still_one_entry(self):
        self.create(**self.doc())
        data = parse_frontmatter(self.read("doc-x.md"))
        self.assertEqual((data["when"], len(data["source_attribution"])), (["w"], 1))

    def test_duplicates_and_repeated_scalars_are_refused(self):
        for params in (self.doc(source=[self.uri_a, self.uri_a]), self.doc(when=["a", "a"]), self.doc(title=["T", "U"])):
            with self.subTest(params=params):
                with self.assertRaises(ActionError):
                    self.create(**params)
        self.assertFalse((self.root / "doc-x.md").exists())

    def test_other_actions_refuse_a_repeated_parameter(self):
        self.create(**self.doc())
        self.create(**self.doc(id="doc-y"))
        with self.assertRaises(ActionError) as caught:
            run_action(self.root, "add-link", {"source": ["doc-x", "doc-y"], "link_type": "compares", "target": "doc-y"})
        self.assertIn("one value", str(caught.exception))


class TestInterfaceLessType(TypedCase):
    def test_a_minimal_template_is_generated_and_verify_accepts_it(self):
        self.create(id="plain", object_type="entity", title="Plain")
        text = self.read("entities/plain.md")
        data = parse_frontmatter(text)
        self.assertEqual((data["id"], data["title"], data["object_type"], data["status"]), ("plain", "Plain", "entity", "active"))
        self.assertIn("## Notes", text)
        self.assertEqual(self.verify(claims=True), [])

    def test_document_parameters_are_refused_for_an_interface_less_type(self):
        with self.assertRaises(ActionError) as caught:
            self.create(id="plain", object_type="entity", title="Plain", source=self.uri_a)
        self.assertIn("unknown parameter 'source'", str(caught.exception))

    def test_a_template_file_for_the_type_wins_over_the_generated_one(self):
        (self.root / "_templates" / "entity.md.tmpl").write_text(
            '---\nid: "{{id}}"\ntitle: "{{title}}"\nobject_type: "{{object_type}}"\nstatus: "experimental"\n---\n\n## Custom\n', encoding="utf-8")
        self.create(id="plain", object_type="entity", title="Plain")
        self.assertIn("## Custom", self.read("entities/plain.md"))

    def test_an_entity_can_be_linked_to(self):
        self.create(**self.doc())
        self.create(**self.entity())
        self.replace("ontology.yaml", "to: entity,", "to: [entity, architecture],")
        run_action(self.root, "add-link", {"source": "doc-x", "link_type": "about", "target": "foundry"})
        self.assertIn('target_id: "foundry"', self.read("doc-x.md"))


if __name__ == "__main__":
    unittest.main()
