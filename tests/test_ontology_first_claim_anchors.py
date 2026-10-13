"""C-A3 claim-id anchors and C-A9 tamper tests: every edit that breaks the claim chain must fail verify."""

import shutil
import unittest
from pathlib import Path

from knowledge_builder.verify import verify_root
from tests.pack_support import PackCase, build_basic, write_claim
from tests.test_ontology_support import FIXTURE, run_cli


class TestClaimAnchors(PackCase):
    def setUp(self):
        super().setUp()
        self.atom = build_basic(self.root)

    def named(self, failures, file, text):
        return any(f.startswith(f"[ERROR] {file}") or f.startswith(f"{file}:") for f in failures) and any(text in f for f in failures)

    def test_clean_pack_passes_both_modes(self):
        self.assertEqual(self.verify(claims=False), [])
        self.assertEqual(self.verify(claims=True), [])

    def test_anchor_counts_in_the_anchor_total(self):
        files, anchors, failures, _ = verify_root(self.root, claims=True)
        self.assertEqual((files, anchors, failures), (3, 1, []))

    def test_anchor_id_missing_from_cites_fails(self):
        self.replace("doc-1.md", "id=c1 -->", "id=c2 -->")
        failures = self.verify()
        self.assertTrue(self.named(failures, "doc-1.md", "ease:claim id=c2 is not in this document's cites"), failures)

    def test_cites_without_an_anchor_fails(self):
        self.replace("doc-1.md", "<!-- ease:claim id=c1 -->", "")
        failures = self.verify()
        self.assertTrue(self.named(failures, "doc-1.md", "cites 'c1' but no ease:claim anchor uses it"), failures)

    def test_ease_source_anchor_is_refused_in_a_rule_document(self):
        uri, digest = self.atom["source_uri"], self.atom["source_digest"]
        self.replace("doc-1.md", "<!-- ease:claim id=c1 -->", f'<!-- ease:claim id=c1 -->\n\nMore.\n<!-- ease:source uri={uri} sha256={digest} quote="Alpha holds" -->')
        self.assertTrue(self.named(self.verify(), "doc-1.md", "ease:source anchors are not allowed"))

    def test_extra_attribute_is_malformed(self):
        self.replace("doc-1.md", "id=c1 -->", 'id=c1 quote="x" -->')
        self.assertTrue(self.named(self.verify(), "doc-1.md", "malformed ease:claim anchor"))

    def test_uncited_block_still_fails_and_a_claim_anchor_cites_it(self):
        self.replace("doc-1.md", "<!-- ease:claim id=c1 -->", "<!-- ease:claim id=c1 -->\n\nAnother plain sentence.")
        self.assertTrue(self.named(self.verify(claims=True), "doc-1.md", "uncited block: Another plain sentence."))
        self.replace("doc-1.md", "Another plain sentence.", "Another plain sentence.\n<!-- ease:claim id=c1 -->")
        self.assertEqual(self.verify(claims=True), [])

    def test_document_with_no_claim_anchor_reports_no_claim_checked(self):
        self.replace("doc-1.md", "Alpha holds in every case.\n<!-- ease:claim id=c1 -->", "Observed: nothing cited.")
        failures = self.verify(claims=True)
        self.assertTrue(self.named(failures, "doc-1.md", "no claim was checked"), failures)

    def test_claim_quote_is_checked_against_the_capture_bytes(self):
        self.replace("claims/c1.md", 'quote: "Alpha holds in every case."', 'quote: "Alpha never holds."')
        self.assertEqual(self.verify(claims=False), [])  # structural mode does not read quotes
        self.assertTrue(self.named(self.verify(claims=True), "claims/c1.md", "quote is not in the capture file"))

    def test_legacy_ease_source_anchor_unchanged_outside_ontology_mode(self):
        legacy = Path(self._tmp.name) / "legacy"
        shutil.copytree(FIXTURE, legacy)
        (legacy / "ontology.yaml").unlink()
        before = verify_root(legacy, claims=True)
        (legacy / "alpha.md").write_text((legacy / "alpha.md").read_text() + "\n<!-- ease:claim id=ghost -->\n")
        self.assertEqual(verify_root(legacy, claims=True), before)  # ease:claim is only a comment outside ontology mode
        self.assertEqual(before[2], [])


class TestTamper(PackCase):
    """C-A9: each of these edits must turn a green pack red, naming the file."""

    def setUp(self):
        super().setUp()
        self.atom = build_basic(self.root)
        self.assertEqual(self.verify(), [])

    def assert_red(self, file, fragment):
        failures = self.verify(claims=True)
        self.assertTrue(any(file in f and fragment in f for f in failures), failures)

    def test_edit_a_claim_quote(self):
        self.replace("claims/c1.md", 'quote: "Alpha holds in every case."', 'quote: "Alpha holds sometimes."')
        self.assert_red("claims/c1.md", "quote is not in the capture file")

    def test_edit_a_capture_byte(self):
        path = self.root / self.atom["source_uri"]
        path.write_bytes(path.read_bytes().replace(b"Alpha", b"Alpho"))
        self.assert_red("sources/s1.md", "sha256 mismatch")

    def test_edit_a_capture_sha_in_the_source(self):
        self.replace("sources/s1.md", self.atom["source_digest"], "0" * 64)
        self.assert_red("sources/s1.md", "sha256 mismatch")

    def test_delete_a_cited_claim(self):
        (self.root / "claims" / "c1.md").unlink()
        self.assert_red("doc-1.md", "target 'c1' does not exist")

    def test_delete_a_source_a_claim_rests_on(self):
        (self.root / "sources" / "s1.md").unlink()
        self.assert_red("claims/c1.md", "evidence source 's1' is not a source object")

    def test_anchor_id_not_in_cites(self):
        self.replace("doc-1.md", "id=c1 -->", "id=zzz -->")
        self.assert_red("doc-1.md", "not in this document's cites")

    def test_cites_unused(self):
        self.replace("doc-1.md", "<!-- ease:claim id=c1 -->", "")
        self.assert_red("doc-1.md", "no ease:claim anchor uses it")

    def test_atom_removed_from_the_ledger(self):
        (self.root / "_evidence" / "r1" / "evidence.jsonl").write_text("")
        self.assert_red("claims/c1.md", "is not in run 'r1'")

    def test_evidence_uri_not_a_capture_of_the_source(self):
        self.replace("claims/c1.md", 'evidence_uri: "_evidence/r1/sources/s1.txt"', 'evidence_uri: "_evidence/r1/sources/other.txt"')
        self.assert_red("claims/c1.md", "is not a capture of source 's1'")

    def test_statement_drift_between_frontmatter_and_body(self):
        self.replace("claims/c1.md", "## Statement\n\nAlpha holds in every case.", "## Statement\n\nSomething else.")
        self.assert_red("claims/c1.md", "## Statement section must repeat the statement")

    def test_cli_verify_claims_exits_1_on_tamper(self):
        self.replace("claims/c1.md", 'quote: "Alpha holds in every case."', 'quote: "gone"')
        code, out, _err = run_cli(["knowledge-builder", "verify", str(self.root), "--claims"])
        self.assertEqual(code, 1)
        self.assertIn("claims/c1.md", out)

    def test_contradiction_claim_needs_a_contradicts_link(self):
        write_claim(self.root, "c1", "s1", self.atom["source_uri"], "Alpha holds in every case.", claim_type="CONTRADICTION")
        self.assert_red("claims/c1.md", "needs a contradicts link")


if __name__ == "__main__":
    unittest.main()
