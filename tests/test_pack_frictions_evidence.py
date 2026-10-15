"""F-1 first-party local evidence and F-4 backfill atoms stay out of saturation."""

import json
import tempfile
import unittest
from pathlib import Path

from knowledge_builder.ontology.actions import ActionError, run_action
from knowledge_builder.ontology.claim_publishers import publisher_count
from knowledge_builder.ontology.objects import load_graph
from knowledge_builder.ontology.schema import load_ontology
from knowledge_builder.pack import graph_counts
from tests.pack_support import FETCHED, RUN, PackCase, add_atom, scaffold_root, sha
from tests.test_run_measure_and_state_set import ATOMS, _atom, _init, _measure, _state


def add_local_atom(root, atom_id, stem, body, meta=None):
    """A local execution output: frozen file with no Source-URL header, atom with no metadata.url."""
    data = f"{body}\n".encode("utf-8")
    (Path(root) / "_evidence" / RUN / "sources" / f"{stem}.txt").write_bytes(data)
    atom = {
        "id": atom_id, "run_id": RUN, "claim_type": "FACT", "statement": f"Statement for {atom_id}.",
        "source_uri": f"_evidence/{RUN}/sources/{stem}.txt", "source_digest": sha(data), "captured_at": FETCHED,
        "confidence": "HIGH", "verified_by_code": False, "metadata": meta or {}, "quote": body,
    }
    with (Path(root) / "_evidence" / RUN / "evidence.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(atom) + "\n")


class TestFirstParty(PackCase):
    def setUp(self):
        super().setUp()
        scaffold_root(self.root)
        add_local_atom(self.root, "l1", "run-output", "exit code 0 after 3 retries")

    def test_starter_kind_enum_gains_first_party(self):
        values = load_ontology(self.root).declared_properties("source")["kind"]["values"]
        self.assertEqual(values, ["official", "academic", "vendor", "practitioner", "community", "first-party"])

    def test_local_file_without_url_promotes_with_publisher_local(self):
        run_action(self.root, "promote-claim", {"atom": "l1", "kind": "first-party"})
        (source,) = (self.root / "sources").glob("*.md")
        text = source.read_text(encoding="utf-8")
        self.assertIn('kind: "first-party"', text)
        self.assertIn('publisher: "local"', text)
        self.assertIn('url: "local:_evidence/r1/sources/run-output.txt"', text)
        self.assertEqual(self.verify(), [])

    def test_same_local_file_reuses_its_source(self):
        add_local_atom(self.root, "l2", "run-output", "exit code 0 after 3 retries")
        run_action(self.root, "promote-claim", {"atom": "l1", "kind": "first-party"})
        run_action(self.root, "promote-claim", {"atom": "l2", "kind": "first-party"})
        self.assertEqual(len(list((self.root / "sources").glob("*.md"))), 1)

    def test_url_less_atom_still_refused_for_other_kinds(self):
        with self.assertRaises(ActionError) as caught:
            run_action(self.root, "promote-claim", {"atom": "l1", "kind": "practitioner"})
        self.assertIn("first-party", str(caught.exception))
        self.assertEqual(list((self.root / "sources").glob("*.md")), [])

    def test_first_party_never_counts_toward_independence(self):
        add_atom(self.root, "w1", "web", "Web page fact.", url="https://docs.one.example/guide/")
        run_action(self.root, "promote-claim", {"atom": "l1", "kind": "first-party"})
        self.assertEqual(publisher_count(self.root, RUN, {"l1"}), 0)
        run_action(self.root, "promote-claim", {"atom": "w1", "kind": "official", "into": "statement-for-l1"})
        self.assertEqual(publisher_count(self.root, RUN, {"l1", "w1"}), 1)
        ontology, graph = load_ontology(self.root), load_graph(self.root)
        self.assertEqual(graph_counts.claim_figures(self.root, ontology, graph)["with_2_publishers"], 0)


class TestBackfillExcluded(unittest.TestCase):
    BACKFILL = [
        _atom("k1", 1, False, "q-k1"), _atom("k2", 1, False, "q-k2"),
        _atom("k3", 2, True, "q-k3"), _atom("k4", 3, True, "q-k4"),
    ]

    def atoms(self):
        out = [json.loads(json.dumps(a)) for a in self.BACKFILL]
        for atom in out:
            atom["metadata"]["backfill"] = True
        return ATOMS + out

    def test_backfill_leaves_novelty_and_denominator_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            _init(tmp, atoms=self.atoms())
            code, out, err = _measure(tmp)
        self.assertEqual(code, 0, out + err)
        self.assertIn("round 1: atoms 4, novel 0, before 0, delta n/a (baseline)", out)
        self.assertIn("round 2: atoms 2, novel 1, before 4, delta 0.2500", out)
        self.assertIn("round 3: atoms 3, novel 0, before 6, delta 0.0000", out)
        self.assertIn("backfill atoms: 4 (excluded)", out)

    def test_no_backfill_line_without_backfill_atoms(self):
        with tempfile.TemporaryDirectory() as tmp:
            _init(tmp)
            _, out, _ = _measure(tmp)
        self.assertNotIn("backfill", out)

    def test_write_state_uses_the_corrected_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = _init(tmp, atoms=self.atoms())
            code, out, err = _measure(tmp, "--write-state")
            state = _state(run)
        self.assertEqual(code, 0, out + err)
        self.assertEqual((state["consecutive_low_delta_rounds"], state["last_weighted_delta"]), (1, 0.0))


if __name__ == "__main__":
    unittest.main()
