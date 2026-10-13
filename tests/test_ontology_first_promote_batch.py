"""C-A4: promote-claim batches (one verify, all-or-nothing) and CONTRADICTION promotion."""

import json
import unittest

from knowledge_builder.ontology.actions import ActionError, run_batch
from tests.pack_support import add_atom
from tests.test_ontology_first_promote_claim import PromoteCase
from tests.test_ontology_support import run_cli


class TestBatch(PromoteCase):
    def test_batch_runs_one_verify_and_logs_one_record_per_item(self):
        calls = []

        def verify(root):
            calls.append(1)
            return []

        records = run_batch(self.root, "promote-claim", [
            {"atom": "a1", "kind": "official", "id": "alpha"},
            {"atom": "a2", "into": "alpha", "kind": "community"},
        ], verify=verify)
        self.assertEqual(len(calls), 2)  # baseline + one after all edits
        self.assertEqual(len(records), 2)
        self.assertEqual(len(self.log()), 2)
        self.assertEqual(self.verify(claims=True), [])
        first, second = self.log()
        self.assertEqual(second["before_sha"]["claims/alpha.md"], first["after_sha"]["claims/alpha.md"])  # sha chain continuous

    def test_batch_is_all_or_nothing(self):
        before = sorted(p.name for p in self.root.rglob("*") if p.is_file())
        with self.assertRaises(ActionError):
            run_batch(self.root, "promote-claim", [
                {"atom": "a1", "kind": "official"},
                {"atom": "ghost", "kind": "official"},
            ])
        self.assertEqual(sorted(p.name for p in self.root.rglob("*") if p.is_file()), before)

    def test_cli_batch_jsonl(self):
        batch = self.root.parent / "batch.jsonl"
        batch.write_text('{"atom": "a1", "kind": "official"}\n{"atom": "a2", "kind": "vendor"}\n')
        code, out, err = run_cli(["knowledge-builder", "action", "promote-claim", "--root", str(self.root), "--batch", str(batch)])
        self.assertEqual(code, 0, out + err)
        self.assertEqual(len(self.ids("claims")), 2)

    def test_batch_is_refused_for_other_actions(self):
        with self.assertRaises(ActionError):
            run_batch(self.root, "deprecate", [{"target": "a", "replacement": "b"}, {"target": "c", "replacement": "d"}])


class TestContradiction(PromoteCase):
    def setUp(self):
        super().setUp()
        add_atom(self.root, "x1", "page-x", "Edges are first class.", url="https://x.example/a")
        add_atom(self.root, "x2", "page-y", "Edges are not first class.", claim_type="CONTRADICTION", url="https://y.example/b",
                 extra={"contradicts": "x1"})

    def test_promoting_a_contradiction_promotes_the_contradicted_atom_and_links_them(self):
        self.promote(atom="x2")
        self.assertEqual(len(self.ids("claims")), 2)
        contradiction = next(p for p in (self.root / "claims").glob("*.md") if 'claim_type: "CONTRADICTION"' in p.read_text())
        text = contradiction.read_text()
        self.assertIn('link_type: "contradicts"', text)
        self.assertEqual(self.verify(claims=True), [])

    def test_contradicted_atom_already_promoted_is_reused(self):
        self.promote(atom="x1", id="first-class")
        self.promote(atom="x2")
        self.assertEqual(len(self.ids("claims")), 2)
        self.assertIn('target_id: "first-class"', self.read(f"claims/{self.ids('claims')[0]}.md") + self.read(f"claims/{self.ids('claims')[1]}.md"))

    def test_contradiction_without_a_target_atom_is_refused(self):
        add_atom(self.root, "x3", "page-z", "Lonely.", claim_type="CONTRADICTION", url="https://z.example/c")
        with self.assertRaises(ActionError) as caught:
            self.promote(atom="x3")
        self.assertIn("metadata.contradicts", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
