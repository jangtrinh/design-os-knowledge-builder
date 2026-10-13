"""Fix round 2: recording a contradiction does not resolve it. Resolution needs a stated resolution or a
deprecated side, and a claim that still verifies."""

import json
import unittest

from knowledge_builder.ontology.actions import ActionError, run_action
from knowledge_builder.research.ledger_gate import ledger_evaluation_input
from knowledge_builder.research.stopping_gate import evaluate_stopping_gate
from tests.pack_support import PackCase, add_atom, scaffold_root


class ResolutionCase(PackCase):
    def setUp(self):
        super().setUp()
        scaffold_root(self.root)
        self.base = add_atom(self.root, "x1", "page-x", "Edges are first class.", url="https://x.example/a")
        add_atom(self.root, "x2", "page-y", "Edges are not first class.", claim_type="CONTRADICTION", url="https://y.example/b",
                 extra={"contradicts": "x1"})
        run_action(self.root, "promote-claim", {"atom": "x2", "kind": "official", "id": "contra"})
        self.other = "contra"
        self.target = next(p.stem for p in (self.root / "claims").glob("*.md") if p.stem != "contra")

    def unresolved(self):
        return ledger_evaluation_input(self.root, "r1").unresolved_contradictions_count

    def resolve(self, text="Scope differs: plain RDF versus RDF-star."):
        return run_action(self.root, "resolve-contradiction", {"claim": "contra", "resolution": text})


class TestResolution(ResolutionCase):
    def test_promoted_but_unresolved_stays_unresolved_and_the_gate_says_so(self):
        self.assertEqual(self.unresolved(), 1)
        decision = evaluate_stopping_gate(ledger_evaluation_input(self.root, "r1"))
        self.assertEqual(decision.state.value, "DEEPEN")
        self.assertIn("Unresolved contradictions (1)", decision.reason)

    def test_a_resolution_resolves_it(self):
        record = self.resolve()
        self.assertEqual(record["files"], ["claims/contra.md"])
        self.assertIn('resolution: "Scope differs', self.read("claims/contra.md"))
        self.assertEqual(self.unresolved(), 0)
        self.assertEqual(self.verify(claims=True), [])

    def test_a_deprecated_contradicted_claim_resolves_it(self):
        add_atom(self.root, "r9", "page-r", "Replacement fact.", url="https://r.example/z")
        run_action(self.root, "promote-claim", {"atom": "r9", "kind": "official", "id": "replacement"})
        run_action(self.root, "deprecate", {"target": self.target, "replacement": "replacement"})
        self.assertEqual(self.unresolved(), 0)

    def test_a_deprecated_contradiction_claim_resolves_it(self):
        run_action(self.root, "deprecate", {"target": "contra", "replacement": self.target})
        self.assertEqual(self.unresolved(), 0)

    def test_state_json_resolved_is_still_honoured(self):
        state = json.loads(self.read("_evidence/r1/state.json"))
        state["resolved"] = ["x2"]
        self.write("_evidence/r1/state.json", json.dumps(state))
        self.assertEqual(self.unresolved(), 0)


class TestContradictsLinkToDeprecatedClaim(ResolutionCase):
    def test_contradicts_may_point_at_a_deprecated_claim_but_cites_may_not(self):
        add_atom(self.root, "r9", "page-r", "Replacement fact.", url="https://r.example/z")
        run_action(self.root, "promote-claim", {"atom": "r9", "kind": "official", "id": "replacement"})
        run_action(self.root, "deprecate", {"target": self.target, "replacement": "replacement"})
        self.assertEqual(self.verify(claims=True), [])


class TestUnverifiableClaimResolvesNothing(ResolutionCase):
    def setUp(self):
        super().setUp()
        self.resolve()
        self.assertEqual(self.unresolved(), 0)

    def test_tampered_quote(self):
        self.replace("claims/contra.md", 'quote: "Edges are not first class."', 'quote: "Edges are first class."')
        self.assertEqual(self.unresolved(), 1)

    def test_tampered_capture_byte(self):
        path = self.root / "_evidence" / "r1" / "sources" / "page-y.txt"
        path.write_bytes(path.read_bytes().replace(b"Edges", b"Edgez"))
        self.assertEqual(self.unresolved(), 1)

    def test_atom_whose_ledger_entry_names_another_capture(self):
        path = self.root / "_evidence/r1/evidence.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        next(r for r in rows if r["id"] == "x2")["source_uri"] = "_evidence/r1/sources/elsewhere.txt"  # the atom no longer names this capture
        path.write_text("".join(json.dumps(r) + "\n" for r in rows))
        self.assertEqual(self.unresolved(), 1)

    def test_tampered_claim_with_a_deprecated_side_still_resolves_nothing(self):
        add_atom(self.root, "r9", "page-r", "Replacement fact.", url="https://r.example/z")
        run_action(self.root, "promote-claim", {"atom": "r9", "kind": "official", "id": "replacement"})
        run_action(self.root, "deprecate", {"target": self.target, "replacement": "replacement"})
        self.assertEqual(self.unresolved(), 0)
        self.replace("claims/contra.md", 'quote: "Edges are not first class."', 'quote: "gone"')
        self.assertEqual(self.unresolved(), 1)

    def test_blank_hand_written_resolution_does_not_count(self):
        self.replace("claims/contra.md", 'resolution: "Scope differs: plain RDF versus RDF-star."', 'resolution: "   "')
        self.assertEqual(self.unresolved(), 1)


class TestResolveContradictionAction(ResolutionCase):
    def test_refuses_a_claim_that_is_not_a_contradiction(self):
        with self.assertRaises(ActionError) as caught:
            run_action(self.root, "resolve-contradiction", {"claim": self.target, "resolution": "text"})
        self.assertIn("claim-type-is", str(caught.exception))
        self.assertNotIn("resolution:", self.read(f"claims/{self.target}.md"))

    def test_refuses_blank_text_and_unknown_claim(self):
        with self.assertRaises(ActionError):
            run_action(self.root, "resolve-contradiction", {"claim": "contra", "resolution": "   "})
        with self.assertRaises(ActionError):
            run_action(self.root, "resolve-contradiction", {"claim": "ghost", "resolution": "text"})
        self.assertNotIn("resolution:", self.read("claims/contra.md"))

    def test_logs_one_line_and_resolution_can_be_rewritten(self):
        self.resolve("first")
        self.resolve("second")
        self.assertIn('resolution: "second"', self.read("claims/contra.md"))
        self.assertEqual(len((self.root / "_actions" / "actions.jsonl").read_text().splitlines()), 3)  # promote + 2 resolves


if __name__ == "__main__":
    unittest.main()
