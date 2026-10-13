"""C-A4: promote-claim turns a verified ledger atom into claims/<id>.md + sources/<id>.md."""

import json
import unittest

from knowledge_builder.ontology.actions import ActionError, run_action, run_batch
from tests.pack_support import PackCase, add_atom, scaffold_root
from tests.test_ontology_support import run_cli


class PromoteCase(PackCase):
    def setUp(self):
        super().setUp()
        scaffold_root(self.root)
        self.a1 = add_atom(self.root, "a1", "page-one", "Alpha holds in every case.", url="https://docs.one.example/guide/")
        self.a2 = add_atom(self.root, "a2", "page-two", "Alpha also holds under load.", url="https://blog.two.example/post")

    def log(self):
        path = self.root / "_actions" / "actions.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def promote(self, **params):
        params.setdefault("kind", "official")
        return run_action(self.root, "promote-claim", params)

    def ids(self, folder):
        return sorted(p.stem for p in (self.root / folder).glob("*.md"))


class TestPromote(PromoteCase):
    def test_atom_becomes_claim_source_and_supported_by_link(self):
        record = self.promote(atom="a1")
        self.assertEqual(self.ids("claims"), ["statement-for-a1"])
        self.assertEqual(self.ids("sources"), ["docs-one-example-guide"])
        claim = self.read("claims/statement-for-a1.md")
        self.assertIn('claim_type: "FACT"', claim)
        self.assertIn('atom_ids: ["a1"]', claim)
        self.assertIn('target_id: "docs-one-example-guide"', claim)
        source = self.read("sources/docs-one-example-guide.md")
        self.assertIn('url: "https://docs.one.example/guide/"', source)
        self.assertIn('publisher: "docs.one.example"', source)
        self.assertIn('fetched: "2026-10-13T05:00:00+00:00"', source)
        self.assertEqual(self.verify(claims=True), [])
        self.assertEqual(sorted(record["files"]), ["claims/statement-for-a1.md", "sources/docs-one-example-guide.md"])

    def test_explicit_id_is_used_and_a_taken_id_is_refused(self):
        self.promote(atom="a1", id="alpha-holds")
        self.assertEqual(self.ids("claims"), ["alpha-holds"])
        with self.assertRaises(ActionError) as caught:
            self.promote(atom="a2", id="alpha-holds")
        self.assertIn("alpha-holds", str(caught.exception))

    def test_same_statement_head_gets_a_numeric_suffix(self):
        add_atom(self.root, "a3", "page-three", "Gamma.", statement="Statement for a1.", url="https://three.example/x")
        self.promote(atom="a1")
        self.promote(atom="a3")
        self.assertEqual(self.ids("claims"), ["statement-for-a1", "statement-for-a1-2"])

    def test_already_promoted_atom_is_refused_naming_the_claim(self):
        self.promote(atom="a1")
        with self.assertRaises(ActionError) as caught:
            self.promote(atom="a1")
        self.assertIn("already promoted to claim 'statement-for-a1'", str(caught.exception))

    def test_unverified_atom_is_refused_by_criteria_not_by_post_verify(self):
        path = self.root / "_evidence" / "r1" / "evidence.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[0]["source_digest"] = "0" * 64
        path.write_text("".join(json.dumps(r) + "\n" for r in rows))
        with self.assertRaises(ActionError) as caught:
            self.promote(atom="a1")
        self.assertIn("sha256 does not match", str(caught.exception))
        self.assertNotIn("verify failed", str(caught.exception))
        self.assertEqual(self.ids("claims"), [])

    def test_quote_missing_from_the_file_is_refused(self):
        add_atom(self.root, "a4", "page-four", "Real text.", quote="Invented text.", url="https://four.example/x")
        with self.assertRaises(ActionError) as caught:
            self.promote(atom="a4")
        self.assertIn("quote is not in the frozen file", str(caught.exception))

    def test_unknown_atom_and_unknown_parameter(self):
        with self.assertRaises(ActionError):
            self.promote(atom="ghost")
        with self.assertRaises(ActionError) as caught:
            self.promote(atom="a1", bogus="x")
        self.assertIn("unknown parameter 'bogus'", str(caught.exception))

    def test_new_source_needs_a_valid_kind_but_a_reused_one_does_not(self):
        with self.assertRaises(ActionError) as caught:
            run_action(self.root, "promote-claim", {"atom": "a1"})
        self.assertIn("kind", str(caught.exception))
        with self.assertRaises(ActionError):
            self.promote(atom="a1", kind="bogus")
        self.promote(atom="a1")
        add_atom(self.root, "a5", "page-one-again", "Again.", url="https://docs.one.example/guide")
        run_action(self.root, "promote-claim", {"atom": "a5"})  # same url (trailing slash ignored): source reused
        self.assertEqual(self.ids("sources"), ["docs-one-example-guide"])
        self.assertIn("page-one-again.txt", self.read("sources/docs-one-example-guide.md"))
        self.assertEqual(self.verify(claims=True), [])

    def test_log_line_per_promotion(self):
        self.promote(atom="a1")
        (line,) = self.log()
        self.assertEqual(line["action"], "promote-claim")
        self.assertEqual(line["params"]["atom"], "a1")
        self.assertTrue(all(v is None for v in line["before_sha"].values()))


class TestInto(PromoteCase):
    def test_into_adds_a_supporting_atom_and_source(self):
        self.promote(atom="a1", id="alpha")
        self.promote(atom="a2", into="alpha")
        claim = self.read("claims/alpha.md")
        self.assertIn('atom_ids: ["a1", "a2"]', claim)
        self.assertEqual(claim.count("supported-by"), 2)
        self.assertEqual(self.ids("sources"), ["blog-two-example-post", "docs-one-example-guide"])
        self.assertEqual(self.verify(claims=True), [])

    def test_into_unknown_or_deprecated_claim_and_type_mismatch(self):
        with self.assertRaises(ActionError):
            self.promote(atom="a2", into="ghost")
        self.promote(atom="a1", id="alpha")
        add_atom(self.root, "f1", "page-f", "A failure.", claim_type="FAILURE_MODE", url="https://f.example/x")
        with self.assertRaises(ActionError) as caught:
            self.promote(atom="f1", into="alpha")
        self.assertIn("claim_type", str(caught.exception))

    def test_into_with_the_same_atom_twice_is_refused(self):
        self.promote(atom="a1", id="alpha")
        with self.assertRaises(ActionError) as caught:
            self.promote(atom="a1", into="alpha")
        self.assertIn("already promoted", str(caught.exception))


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

    def test_contradiction_resolves_the_gate_through_the_claim_not_state_json(self):
        from knowledge_builder.research.ledger_gate import ledger_evaluation_input

        before = ledger_evaluation_input(self.root, "r1").unresolved_contradictions_count
        self.promote(atom="x2")
        after = ledger_evaluation_input(self.root, "r1").unresolved_contradictions_count
        self.assertEqual((before, after), (1, 0))
        self.assertEqual(json.loads(self.read("_evidence/r1/state.json"))["resolved"], [])


if __name__ == "__main__":
    unittest.main()
