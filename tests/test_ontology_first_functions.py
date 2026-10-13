"""C-A6 claim lifecycle and C-A7 functions that traverse document -> claim -> source."""

import datetime
import hashlib
import unittest

from knowledge_builder.ontology.actions import ActionError, run_action
from knowledge_builder.ontology.functions import FUNCTIONS, Context
from knowledge_builder.ontology.objects import load_graph
from tests.pack_support import PackCase, add_atom, build_basic, scaffold_root, write_claim, write_document, write_source
from tests.test_ontology_support import make_stop_run


def call(root, name, *args):
    return FUNCTIONS[name](Context(root, load_graph(root)), *args)


class TestClaimLifecycle(PackCase):
    def setUp(self):
        super().setUp()
        scaffold_root(self.root)
        add_atom(self.root, "a1", "p1", "First fact holds.", url="https://one.example/a")
        add_atom(self.root, "a2", "p2", "Second fact holds.", url="https://two.example/b")
        run_action(self.root, "promote-claim", {"atom": "a1", "kind": "official", "id": "old-claim"})
        run_action(self.root, "promote-claim", {"atom": "a2", "kind": "official", "id": "new-claim"})

    def test_promoted_claims_are_active(self):
        self.assertIn('status: "active"', self.read("claims/old-claim.md"))

    def test_deprecating_a_claim_is_one_action(self):
        record = run_action(self.root, "deprecate", {"target": "old-claim", "replacement": "new-claim"})
        self.assertEqual(record["files"], ["claims/old-claim.md"])
        self.assertIn('status: "deprecated"', self.read("claims/old-claim.md"))
        self.assertIn('superseded_by: "new-claim"', self.read("claims/old-claim.md"))
        self.assertEqual(self.verify(claims=True), [])

    def test_a_citing_document_blocks_deprecation_and_is_named(self):
        atom = add_atom(self.root, "a3", "p3", "Third.", url="https://three.example/c")
        write_document(self.root, "doc-1", ["old-claim"], ["Some text.", "<!-- ease:claim id=old-claim -->"], atom["source_uri"], atom["source_digest"])
        before = self.read("claims/old-claim.md")
        with self.assertRaises(ActionError) as caught:
            run_action(self.root, "deprecate", {"target": "old-claim", "replacement": "new-claim"})
        message = str(caught.exception)
        self.assertIn("doc-1.md", message)
        self.assertIn("use 'new-claim'", message)
        self.assertEqual(self.read("claims/old-claim.md"), before)


class TestTraversal(PackCase):
    def setUp(self):
        super().setUp()
        self.atom = build_basic(self.root)

    def days_since(self, iso):
        return (datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(iso)).days

    def test_evidence_age_follows_document_claim_source_captures(self):
        self.replace("sources/s1.md", 'fetched: "2026-10-13T05:00:00+00:00"', 'fetched: "2020-01-01T00:00:00+00:00"')
        expected = self.days_since("2020-01-01T00:00:00+00:00")
        self.assertEqual(call(self.root, "evidence-age-days", "doc-1"), expected)
        self.assertEqual(call(self.root, "evidence-age-days", "c1"), expected)
        self.assertEqual(call(self.root, "evidence-age-days", "s1"), expected)

    def test_evidence_age_is_the_oldest_cited_capture(self):
        extra = add_atom(self.root, "a2", "s2", "Beta holds too.", url="https://s2.example/page")
        write_source(self.root, "s2", extra["source_uri"], extra["source_digest"], publisher="s2.example")
        self.replace("sources/s2.md", 'fetched: "2026-10-13T05:00:00+00:00"', 'fetched: "2019-05-05T00:00:00+00:00"')
        write_claim(self.root, "c2", "s2", extra["source_uri"], "Beta holds too.", atom="a2")
        self.replace("doc-1.md", '    target_id: "c1"\n', '    target_id: "c1"\n  - link_type: "cites"\n    target_id: "c2"\n')
        self.replace("doc-1.md", "<!-- ease:claim id=c1 -->", "<!-- ease:claim id=c1 -->\n\nBeta holds too.\n<!-- ease:claim id=c2 -->")
        self.assertEqual(self.verify(), [])
        self.assertEqual(call(self.root, "evidence-age-days", "doc-1"), self.days_since("2019-05-05T00:00:00+00:00"))

    def test_source_count_is_distinct_publishers_not_files(self):
        self.assertEqual(call(self.root, "source-count", "doc-1"), 1)
        extra = add_atom(self.root, "a2", "s2", "Alpha holds in every case.", url="https://example.com/other")
        write_source(self.root, "s2", extra["source_uri"], extra["source_digest"], publisher="example.com")  # same publisher
        self.replace("claims/c1.md", 'atom_ids: ["a1"]', 'atom_ids: ["a1", "a2"]')
        self.replace("claims/c1.md", "link_types:\n", 'link_types:\n  - link_type: "supported-by"\n    target_id: "s2"\n')
        text = self.read("claims/c1.md").replace("link_types:", f'  - atom: "a2"\n    run: "r1"\n    source: "s2"\n    evidence_uri: "{extra["source_uri"]}"\n    quote: "Alpha holds in every case."\nlink_types:', 1)
        self.write("claims/c1.md", text)
        self.assertEqual(self.verify(), [])
        self.assertEqual(call(self.root, "source-count", "c1"), 1)  # two sources, one publisher
        write_source(self.root, "s2", extra["source_uri"], extra["source_digest"], publisher="other.org")
        self.assertEqual(call(self.root, "source-count", "c1"), 2)

    def test_claims_verified_covers_the_cited_claims_and_their_sources(self):
        self.assertTrue(call(self.root, "claims-verified", "doc-1"))
        self.replace("claims/c1.md", 'quote: "Alpha holds in every case."', 'quote: "tampered"')
        self.assertFalse(call(self.root, "claims-verified", "doc-1"))  # the failure sits in the claim file, not the document


class TestRunsStopSufficientThroughClaims(PackCase):
    def setUp(self):
        super().setUp()
        scaffold_root(self.root)
        make_stop_run(self.root, "run-1")
        body = (self.root / "_evidence/run-1/sources/source.txt").read_bytes()
        self.uri = "_evidence/run-1/sources/source.txt"
        self.digest = hashlib.sha256(body).hexdigest()
        write_source(self.root, "src-1", self.uri, self.digest)
        write_claim(self.root, "c1", "src-1", self.uri, "Alpha facts live here.", atom="atom-c1", run="run-1")
        write_document(self.root, "doc-1", ["c1"], ["Alpha facts live here.", "<!-- ease:claim id=c1 -->"], self.uri, self.digest)
        fail_uri = "_evidence/run-1/sources/failure.txt"  # the run's second atom, from a second publisher
        write_source(self.root, "src-fail", fail_uri, hashlib.sha256((self.root / fail_uri).read_bytes()).hexdigest(), publisher="other.org")
        write_claim(self.root, "c-fail", "src-fail", fail_uri, "known failure mode", atom="atom-fail", claim_type="FAILURE_MODE", run="run-1")

    def test_stopped_run_behind_the_claim_passes(self):
        self.assertEqual(self.verify(), [])
        self.assertTrue(call(self.root, "runs-stop-sufficient", "doc-1", "verified"))

    def test_a_claim_in_an_unfinished_run_blocks_the_tier_even_when_the_document_lists_a_stopped_run(self):
        other = add_atom(self.root, "b1", "unfinished", "Unfinished run fact.", url="https://u.example/x")  # run r1: not stopped
        write_source(self.root, "src-2", other["source_uri"], other["source_digest"], publisher="u.example")
        write_claim(self.root, "c2", "src-2", other["source_uri"], "Unfinished run fact.", atom="b1")
        self.replace("doc-1.md", '    target_id: "c1"\n', '    target_id: "c1"\n  - link_type: "cites"\n    target_id: "c2"\n')
        self.replace("doc-1.md", "<!-- ease:claim id=c1 -->", "<!-- ease:claim id=c1 -->\n\nUnfinished run fact.\n<!-- ease:claim id=c2 -->")
        self.assertEqual(self.verify(), [])
        self.assertFalse(call(self.root, "runs-stop-sufficient", "doc-1", "verified"))
        self.assertTrue(call(self.root, "runs-stop-sufficient", "doc-1", "draft"))


if __name__ == "__main__":
    unittest.main()
