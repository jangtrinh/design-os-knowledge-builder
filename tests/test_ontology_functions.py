"""A7: built-in function registry only; nothing is imported or executed from the root."""

import unittest

from knowledge_builder.ontology.functions import FUNCTIONS, Context
from knowledge_builder.ontology.objects import load_graph
from knowledge_builder.ontology.schema import OntologyError, load_ontology
import hashlib

from tests.test_ontology_support import RootCase, make_stop_run


class TestFunctions(RootCase):
    def ctx(self):
        return Context(self.root, load_graph(self.root))

    def test_registry_is_exactly_the_designed_set(self):
        self.assertEqual(
            sorted(FUNCTIONS),
            ["claim-type-is", "claims-verified", "evidence-age-days", "has-link", "links-in-count", "non-blank", "object-exists", "runs-stop-sufficient", "source-count", "status-is"],
        )

    def test_predicates(self):
        ctx = self.ctx()
        self.assertTrue(FUNCTIONS["object-exists"](ctx, "alpha"))
        self.assertFalse(FUNCTIONS["object-exists"](ctx, "nope"))
        self.assertTrue(FUNCTIONS["status-is"](ctx, "alpha", "active"))
        self.assertTrue(FUNCTIONS["status-is"](ctx, "cmp", "experimental"))
        self.assertFalse(FUNCTIONS["status-is"](ctx, "nope", "active"))
        self.assertTrue(FUNCTIONS["has-link"](ctx, "beta", "depends-on", "alpha"))
        self.assertFalse(FUNCTIONS["has-link"](ctx, "alpha", "depends-on", "beta"))

    def test_derived_values(self):
        ctx = self.ctx()
        self.assertEqual(FUNCTIONS["source-count"](ctx, "alpha"), 1)
        self.assertEqual(FUNCTIONS["links-in-count"](ctx, "alpha"), 2)
        self.assertEqual(FUNCTIONS["links-in-count"](ctx, "cmp"), 0)
        self.assertGreaterEqual(FUNCTIONS["evidence-age-days"](ctx, "alpha"), 0)

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(self.root.rglob("*")) if p.is_file()}

    def test_runs_stop_sufficient_needs_every_cited_run_to_stop(self):
        gate = FUNCTIONS["runs-stop-sufficient"]
        self.assertFalse(gate(self.ctx(), "alpha", "verified"))  # run-1 has no state.json
        make_stop_run(self.root)
        before = self.snapshot()
        self.assertTrue(gate(self.ctx(), "alpha", "verified"))
        self.assertEqual(self.snapshot(), before)  # read-only
        (self.root / "_evidence/run-1/review.json").unlink()  # any other decision fails
        self.assertFalse(gate(self.ctx(), "alpha", "verified"))

    def test_runs_stop_sufficient_counts_runs_cited_by_anchors_too(self):
        make_stop_run(self.root)
        self.replace("alpha.md", "<!-- ease:source uri=_evidence/run-1/sources/source.txt",
                     "<!-- ease:source uri=_evidence/run-2/sources/other.txt sha256=" + "0" * 64 + " quote=\"x\" -->\n<!-- ease:source uri=_evidence/run-1/sources/source.txt")
        self.assertFalse(FUNCTIONS["runs-stop-sufficient"](self.ctx(), "alpha", "verified"))

    def test_runs_stop_sufficient_only_guards_the_verified_tier(self):
        self.assertTrue(FUNCTIONS["runs-stop-sufficient"](self.ctx(), "alpha", "community_reference"))

    def test_object_citing_no_run_cannot_reach_verified(self):
        self.replace("alpha.md", "_evidence/run-1/sources/source.txt\"\n    sha256", "docs/x.txt\"\n    sha256")
        self.assertFalse(FUNCTIONS["runs-stop-sufficient"](self.ctx(), "alpha", "verified"))

    def test_claims_verified_follows_the_quote_check(self):
        self.assertTrue(FUNCTIONS["claims-verified"](self.ctx(), "alpha"))
        self.replace("alpha.md", 'quote="Alpha facts live here."', 'quote="Not in the source."')
        self.assertFalse(FUNCTIONS["claims-verified"](self.ctx(), "alpha"))
        self.assertTrue(FUNCTIONS["claims-verified"](self.ctx(), "beta"))

    def test_evidence_age_reads_the_oldest_fetched_line(self):
        src = self.root / "_evidence/run-1/sources/source.txt"
        src.write_text("Source-URL: https://x\nFetched: 2026-10-01T00:00:00+00:00\n\nAlpha facts live here. Beta facts live here.\n", encoding="utf-8")
        age = FUNCTIONS["evidence-age-days"](self.ctx(), "alpha")
        import datetime
        expected = (datetime.datetime.now(datetime.timezone.utc) - datetime.datetime(2026, 10, 1, tzinfo=datetime.timezone.utc)).days
        self.assertEqual(age, expected)
        self.assertGreater(age, 0)  # mtime is today, so a Fetched line must win

    def test_evidence_age_takes_the_oldest_source_and_falls_back_to_mtime(self):
        import os, time
        old = self.root / "_evidence/run-1/sources/old.txt"
        old.write_text("Fetched: 2026-01-01T00:00:00Z\nbody\n", encoding="utf-8")
        self.replace("alpha.md", "  - uri: \"_evidence/run-1/sources/source.txt\"", "  - uri: \"_evidence/run-1/sources/old.txt\"\n    sha256: \"" + "0" * 64 + "\"\n  - uri: \"_evidence/run-1/sources/source.txt\"")
        oldest = FUNCTIONS["evidence-age-days"](self.ctx(), "alpha")
        self.assertGreaterEqual(oldest, 200)
        old.write_text("no fetched line here\n", encoding="utf-8")
        os.utime(old, (time.time() - 3 * 86400, time.time() - 3 * 86400))
        self.assertEqual(FUNCTIONS["evidence-age-days"](self.ctx(), "alpha"), 3)

    def test_root_code_is_never_loaded(self):
        marker = self.root / "executed.txt"
        (self.root / "functions.py").write_text(f"open({str(marker)!r}, 'w').write('x')\n", encoding="utf-8")
        (self.root / "sneaky.py").write_text(f"open({str(marker)!r}, 'w').write('x')\n", encoding="utf-8")
        self.write("ontology.yaml", self.read("ontology.yaml") + "action_types:\n  x:\n    criteria: [{function: sneaky, args: [a]}]\n")
        with self.assertRaises(OntologyError):
            load_ontology(self.root)
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
