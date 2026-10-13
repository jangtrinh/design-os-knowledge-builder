"""C-A1 / C-A2: interface-scoped verify, folder routing, and the starter template."""

import shutil
import unittest
from pathlib import Path

from knowledge_builder.ontology.schema import OntologyError, load_ontology
from knowledge_builder.verify import verify_root
from tests.pack_support import PackCase, build_basic, scaffold_root
from tests.test_ontology_support import FIXTURE


class TestStarterTemplate(PackCase):
    def test_starter_loads_with_declared_shapes(self):
        scaffold_root(self.root)
        onto = load_ontology(self.root)
        self.assertEqual(sorted(onto.implementing("sourced-document")), ["comparison", "concept", "decision-record", "guide"])
        self.assertEqual(onto.object_types["claim"]["folder"], "claims")
        self.assertEqual(onto.object_types["source"]["folder"], "sources")
        names = set(onto.link_types)
        self.assertTrue({"cites", "supported-by", "contradicts", "compares", "depends-on", "about"} <= names)
        self.assertEqual(onto.interfaces["sourced-document"]["rules"], ["anchors-match-cited-claims"])

    def test_source_kind_is_an_enum(self):
        scaffold_root(self.root)
        values = load_ontology(self.root).declared_properties("source")["kind"]["values"]
        self.assertEqual(values, ["official", "academic", "vendor", "practitioner", "community"])

    def test_templates_exist_for_every_starter_type(self):
        scaffold_root(self.root)
        for kind in ("concept", "guide", "comparison", "decision-record", "claim", "source"):
            self.assertTrue((self.root / "_templates" / f"{kind}.md.tmpl").is_file(), kind)


class TestScopedVerify(PackCase):
    def test_claim_and_source_files_verify_clean_under_their_own_interfaces(self):
        build_basic(self.root)
        self.assertEqual(self.verify(claims=False), [])
        self.assertEqual(self.verify(claims=True), [])

    def test_document_still_gets_v1_checks(self):
        build_basic(self.root)
        self.replace("doc-1.md", "## Purpose", "## Intro")
        failures = self.verify(claims=False)
        self.assertTrue(any("doc-1.md" in f and "missing heading ## Purpose" in f for f in failures), failures)

    def test_v1_checks_never_run_on_claim_or_source(self):
        build_basic(self.root)
        failures = self.verify(claims=True)
        self.assertFalse([f for f in failures if f.startswith(("claims/", "sources/"))])

    def test_claim_is_not_excluded_from_the_walk(self):
        build_basic(self.root)
        files, _anchors, _failures, _exempt = verify_root(self.root)
        self.assertEqual(files, 3)  # doc-1, claims/c1, sources/s1

    def test_legacy_root_has_no_scoping(self):
        legacy = Path(self._tmp.name) / "legacy"
        shutil.copytree(FIXTURE, legacy)
        (legacy / "ontology.yaml").unlink()
        (legacy / "alpha.md").write_text("---\nid: \"alpha\"\n---\nbody\n", encoding="utf-8")
        failures = verify_root(legacy)[2]
        self.assertTrue(any("alpha.md: missing title" in f for f in failures), failures)
        self.assertTrue(any("alpha.md: missing heading ## Purpose" in f for f in failures), failures)


class TestFolderRouting(PackCase):
    def test_claim_outside_its_folder_fails(self):
        build_basic(self.root)
        (self.root / "claims" / "c1.md").rename(self.root / "c1.md")
        failures = self.verify(claims=False)
        self.assertTrue(any("c1.md" in f and "folder" in f and "claims" in f for f in failures), failures)

    def test_source_in_claims_folder_fails(self):
        build_basic(self.root)
        (self.root / "sources" / "s1.md").rename(self.root / "claims" / "s1.md")
        failures = self.verify(claims=False)
        self.assertTrue(any("claims/s1.md" in f and "folder" in f for f in failures), failures)

    def test_bad_folder_value_is_a_load_error(self):
        scaffold_root(self.root)
        text = (self.root / "ontology.yaml").read_text().replace("folder: claims", "folder: ../claims")
        (self.root / "ontology.yaml").write_text(text)
        with self.assertRaises(OntologyError):
            load_ontology(self.root)

    def test_unknown_interface_rule_is_a_load_error(self):
        scaffold_root(self.root)
        text = (self.root / "ontology.yaml").read_text().replace("anchors-match-cited-claims", "no-such-rule")
        (self.root / "ontology.yaml").write_text(text)
        with self.assertRaises(OntologyError):
            load_ontology(self.root)


if __name__ == "__main__":
    unittest.main()
