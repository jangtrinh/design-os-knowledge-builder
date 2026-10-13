"""Cited sources are resolved inside the root: run gate identity, Fetched headers, escapes."""

import os
import time

from knowledge_builder.ontology.functions import FUNCTIONS, Context
from knowledge_builder.ontology.objects import load_graph
from tests.test_ontology_support import RootCase, make_stop_run

CITED = "_evidence/run-1/sources/source.txt"


class CitedCase(RootCase):
    def setUp(self):
        super().setUp()
        self.pristine = self.read("alpha.md")

    def ctx(self):
        return Context(self.root, load_graph(self.root))

    def cite_only(self, uri):
        self.write("alpha.md", self.pristine.replace(CITED, uri))

    def gate(self):
        return FUNCTIONS["runs-stop-sufficient"](self.ctx(), "alpha", "verified")


class TestRunIdentity(CitedCase):
    def setUp(self):
        super().setUp()
        make_stop_run(self.root)
        (self.root / "_evidence/blocked/sources").mkdir(parents=True)  # no state.json: not stopped

    def test_dot_dot_cannot_borrow_another_runs_decision(self):
        self.assertTrue(self.gate())
        self.cite_only("_evidence/run-1/../blocked/sources/x.txt")
        self.assertFalse(self.gate())

    def test_leading_dot_slash_is_normalised_not_ignored(self):
        self.cite_only("./_evidence/blocked/sources/x.txt")
        self.assertFalse(self.gate())
        self.cite_only("./_evidence/run-1/sources/source.txt")
        self.assertTrue(self.gate())

    def test_citations_that_do_not_resolve_inside_a_run_fail_the_criterion(self):
        outside = self.root.parent / "outside.txt"
        outside.write_text("x", encoding="utf-8")
        os.symlink(outside, self.root / "_evidence/run-1/sources/link.txt")
        for uri in ("../outside.txt", "/etc/hosts", "_evidence/run-1/sources/link.txt", "_evidence/run-1/other/x.txt", "_evidence/run-1"):
            with self.subTest(uri):
                self.cite_only(uri)
                self.assertFalse(self.gate())
                self.cite_only(CITED)


class TestFetchedHeader(CitedCase):
    SRC = "_evidence/run-1/sources/source.txt"

    def age(self):
        return FUNCTIONS["evidence-age-days"](self.ctx(), "alpha")

    def test_fetched_counts_only_in_the_leading_capture_header(self):
        path = self.root / self.SRC
        path.write_text("Source-URL: https://x\nFetched: 2020-01-01T00:00:00+00:00\n\nbody\n", encoding="utf-8")
        self.assertGreater(self.age(), 2000)
        path.write_text("Quoted page text.\n\nFetched: 2020-01-01T00:00:00+00:00\n", encoding="utf-8")
        self.assertEqual(self.age(), 0)  # mtime is now
        path.write_text("Intro line\nFetched: 2020-01-01T00:00:00+00:00\n", encoding="utf-8")
        self.assertGreater(self.age(), 2000)  # still inside the header block (no blank line yet)
        path.write_text("\nFetched: 2020-01-01T00:00:00+00:00\n", encoding="utf-8")
        self.assertEqual(self.age(), 0)  # header is empty, so the line is body text
        stamp = time.time() - 5 * 86400
        os.utime(path, (stamp, stamp))
        self.assertEqual(self.age(), 5)


class TestAgeStaysInsideTheRoot(CitedCase):
    def test_escaping_uri_and_symlink_are_ignored(self):
        outside = self.root.parent / "outside-old.txt"
        outside.write_text("Fetched: 2001-01-01T00:00:00+00:00\n\nx\n", encoding="utf-8")
        os.symlink(outside, self.root / "_evidence/run-1/sources/link.txt")
        for uri in ("../outside-old.txt", "_evidence/run-1/sources/link.txt", "/etc/hosts"):
            with self.subTest(uri):
                self.cite_only(uri)
                self.assertIsNone(FUNCTIONS["evidence-age-days"](self.ctx(), "alpha"))
                self.cite_only(CITED)
