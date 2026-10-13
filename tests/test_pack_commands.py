"""C-A8: pack init / status / check."""

import json
import unittest
from pathlib import Path

from knowledge_builder.ontology.actions import run_action
from tests.pack_support import PackCase, add_atom, write_document
from tests.test_ontology_support import run_cli


def pack(*args):
    return run_cli(["knowledge-builder", "pack", *args])


class PackInitCase(PackCase):
    def init(self, *extra):
        return pack("init", "--root", str(self.root), "--topic", "Demo Topic", "--run", "demo-1", *extra)

    def add_atoms(self):
        add_atom(self.root, "a1", "p1", "First fact holds.", url="https://one.example/a", run="demo-1", extra={"round": 1, "novel": True})
        add_atom(self.root, "a2", "p2", "Second fact holds.", url="https://two.example/b", run="demo-1", extra={"round": 1, "novel": True})
        add_atom(self.root, "a3", "p3", "Third fact holds.", url="https://three.example/c", run="demo-1", extra={"round": 2, "novel": True})


class TestInit(PackInitCase):
    def test_scaffolds_the_root(self):
        code, out, err = self.init("--require", "c-one", "--require", "c-two", "--budget", "40")
        self.assertEqual(code, 0, out + err)
        for rel in ("ontology.yaml", "pack.json", "claims", "sources", "_templates/claim.md.tmpl", "_templates/concept.md.tmpl",
                    "_evidence/demo-1/state.json", "_evidence/demo-1/evidence.jsonl", "_evidence/demo-1/sources"):
            self.assertTrue((self.root / rel).exists(), rel)
        state = json.loads(self.read("_evidence/demo-1/state.json"))
        self.assertEqual((state["required_claim_ids"], state["budget_total"]), (["c-one", "c-two"], 40))
        self.assertEqual(json.loads(self.read("pack.json")), {"topic": "Demo Topic", "run": "demo-1"})
        self.assertEqual(self.verify(), [])

    def test_starter_yaml_is_copied_byte_for_byte(self):
        self.init()
        starter = Path(__file__).resolve().parent.parent / "src" / "knowledge_builder" / "templates" / "ontology.starter.yaml"
        self.assertEqual(self.read("ontology.yaml"), starter.read_text())

    def test_refuses_a_non_empty_root_and_changes_nothing(self):
        self.root.mkdir()
        (self.root / "keep.txt").write_text("mine")
        code, out, err = self.init()
        self.assertEqual(code, 1)
        self.assertIn("not empty", err)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["keep.txt"])

    def test_accepts_an_existing_empty_root_and_derives_the_default_run(self):
        self.root.mkdir()
        code, out, err = pack("init", "--root", str(self.root), "--topic", "Demo Topic")
        self.assertEqual(code, 0, out + err)
        run = json.loads(self.read("pack.json"))["run"]
        self.assertRegex(run, r"^demo-topic-\d{6}$")
        self.assertTrue((self.root / "_evidence" / run / "state.json").is_file())

    def test_bad_run_id_leaves_an_empty_root_behind(self):
        code, out, err = pack("init", "--root", str(self.root), "--topic", "T", "--run", "a/b")
        self.assertEqual(code, 1)
        self.assertEqual(list(self.root.iterdir()) if self.root.exists() else [], [])


class TestDocumentTemplates(PackInitCase):
    def test_every_document_type_can_be_created_from_its_packaged_template(self):
        self.init()
        self.add_atoms()
        for kind in ("concept", "guide", "comparison", "decision-record"):
            code, out, err = run_cli([
                "knowledge-builder", "action", "create-object", "--root", str(self.root), "--param", f"id=doc-{kind}",
                "--param", f"object_type={kind}", "--param", "domain=demo", "--param", "title=T", "--param", "description=D",
                "--param", "when=w", "--param", "source=_evidence/demo-1/sources/p1.txt",
            ])
            self.assertEqual(code, 0, out + err)
        self.assertEqual(self.verify(claims=False), [])


class TestStatusAndCheck(PackInitCase):
    def setUp(self):
        super().setUp()
        self.init()
        self.add_atoms()
        run_action(self.root, "promote-claim", {"atom": "a1", "kind": "official", "id": "claim-one"})
        run_action(self.root, "promote-claim", {"atom": "a2", "kind": "vendor", "id": "claim-two"})
        write_document(self.root, "doc-1", ["claim-one"], ["First fact holds.", "<!-- ease:claim id=claim-one -->", "", "Derived: plain synthesis."],
                       "_evidence/demo-1/sources/p1.txt", self.sha("p1"))

    def sha(self, stem):
        import hashlib
        return hashlib.sha256((self.root / f"_evidence/demo-1/sources/{stem}.txt").read_bytes()).hexdigest()

    def status(self):
        code, out, err = pack("status", "--root", str(self.root), "--json")
        self.assertEqual(code, 0, out + err)
        return json.loads(out)

    def test_status_json_counts(self):
        report = self.status()
        self.assertEqual(report["run"], "demo-1")
        self.assertEqual(report["objects"]["by_type"], {"claim": 2, "concept": 1, "source": 2})
        self.assertEqual(report["objects"]["by_status"]["active"], 2)
        self.assertEqual(report["objects"]["by_type_status"]["claim"], {"active": 2})
        self.assertEqual(report["unpromoted_atoms"], 1)
        self.assertEqual(report["uncited_claims"], 1)
        self.assertEqual(report["documents_without_claims"], 0)
        self.assertEqual(report["derived_blocks"], 1)
        self.assertEqual(report["verify"]["failures"], 0)
        self.assertEqual(report["claims"]["count"], 2)

    def test_a_document_without_claims_is_counted_and_fails_the_claims_check(self):
        write_document(self.root, "doc-2", [], ["Derived: nothing cited."], "_evidence/demo-1/sources/p1.txt", self.sha("p1"), object_type="guide")
        report = self.status()
        self.assertEqual((report["documents_without_claims"], report["derived_blocks"]), (1, 2))
        self.assertEqual(report["verify"]["failures"], 1)
        code, out, _err = pack("check", "--root", str(self.root))
        self.assertEqual(code, 1)
        self.assertIn("doc-2.md: no claim was checked", out)

    def test_status_gate_and_saturation(self):
        report = self.status()
        self.assertIn(report["gate"]["decision"], {"DEEPEN", "ABSTAIN_BLOCKED", "PAUSE_BUDGET", "STOP_SUFFICIENT"})
        self.assertTrue(report["gate"]["reason"])
        rounds = report["saturation"]["rounds"]
        self.assertEqual([r["round"] for r in rounds], [1, 2])
        self.assertEqual(rounds[1]["novel"], 0)  # a3 is novel but nothing cites its quote
        self.assertEqual(rounds[0]["novel"], 1)  # only a1's quote is cited by a document

    def test_status_text_is_one_screen(self):
        code, out, err = pack("status", "--root", str(self.root))
        self.assertEqual(code, 0, out + err)
        self.assertLess(len(out.splitlines()), 40)
        for needle in ("claim", "unpromoted atoms: 1", "gate:", "saturation"):
            self.assertIn(needle, out)

    def test_check_exit_0_when_verify_passes_and_prints_the_gate(self):
        code, out, err = pack("check", "--root", str(self.root))
        self.assertEqual(code, 0, out + err)
        self.assertIn("failures: 0", out)
        self.assertIn("gate:", out)

    def test_check_exit_1_on_a_verify_failure_and_prints_it(self):
        self.replace("claims/claim-one.md", 'quote: "First fact holds."', 'quote: "tampered"')
        code, out, err = pack("check", "--root", str(self.root))
        self.assertEqual(code, 1)
        self.assertIn("claims/claim-one.md", out)

    def test_deprecated_claim_lists_the_documents_that_still_cite_it(self):
        self.replace("claims/claim-one.md", 'status: "active"', 'status: "deprecated"\nsuperseded_by: "claim-two"')
        report = self.status()
        self.assertEqual(report["deprecated_claims_cited"], [{"claim": "claim-one", "superseded_by": "claim-two", "documents": ["doc-1"]}])
        code, out, err = pack("check", "--root", str(self.root))
        self.assertEqual(code, 1)
        self.assertIn("claim-one", out)
        self.assertIn("re-link or re-word", out)
        self.assertIn("doc-1", out)

    def test_independence_counts_by_file_and_by_publisher(self):
        add_atom(self.root, "a4", "p4", "First fact holds again.", url="https://one.example/other", run="demo-1")
        run_action(self.root, "promote-claim", {"atom": "a4", "into": "claim-one", "kind": "official"})
        add_atom(self.root, "a5", "p5", "First fact holds, third view.", url="https://elsewhere.example/z", run="demo-1")
        run_action(self.root, "promote-claim", {"atom": "a5", "into": "claim-two", "kind": "official"})
        claims = self.status()["claims"]
        self.assertEqual((claims["with_2_sources_by_file"], claims["with_2_publishers"]), (2, 1))

    def test_duplicate_statements_are_reported(self):
        add_atom(self.root, "d1", "pd", "Dup.", url="https://d.example/z", run="demo-1", statement="First fact holds.")
        add_atom(self.root, "d2", "pe", "Dup2.", url="https://e.example/z", run="demo-1", statement="first   fact HOLDS.")
        run_action(self.root, "promote-claim", {"atom": "d1", "kind": "official", "id": "dup-one"})
        run_action(self.root, "promote-claim", {"atom": "d2", "kind": "official", "id": "dup-two"})
        self.assertEqual(self.status()["claims"]["duplicate_statements"], [["dup-one", "dup-two"]])

    def test_status_of_a_legacy_root_is_refused(self):
        (self.root / "ontology.yaml").unlink()
        code, out, err = pack("status", "--root", str(self.root))
        self.assertEqual(code, 1)
        self.assertIn("ontology.yaml", err)

    def test_status_needs_no_run_when_the_pack_has_none(self):
        (self.root / "pack.json").unlink()
        code, out, err = pack("status", "--root", str(self.root), "--json")
        self.assertEqual(code, 0, out + err)
        report = json.loads(out)
        self.assertIsNone(report["run"])
        self.assertIsNone(report["unpromoted_atoms"])


if __name__ == "__main__":
    unittest.main()
