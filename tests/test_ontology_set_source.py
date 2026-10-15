"""set-source: re-attribute a Source's publisher and/or kind through the same pipeline as every other action."""

import json
import unittest

from knowledge_builder.ontology.actions import ActionError, run_action, run_batch
from knowledge_builder.ontology.claim_publishers import publisher_count
from knowledge_builder.ontology.objects import load_graph
from knowledge_builder.ontology.schema import load_ontology
from knowledge_builder.pack import graph_counts
from tests.pack_support import RUN, PackCase, add_atom, scaffold_root


class SetSourceCase(PackCase):
    def setUp(self):
        super().setUp()
        scaffold_root(self.root)
        add_atom(self.root, "a1", "p1", "First fact.", url="https://arxiv.org/abs/2404.16130")
        add_atom(self.root, "a2", "p2", "Second fact.", url="https://microsoft.github.io/graphrag/")
        run_action(self.root, "promote-claim", {"atom": "a1", "kind": "academic", "publisher": "arxiv-authors", "id": "graphrag"})
        run_action(self.root, "promote-claim", {"atom": "a2", "kind": "official", "into": "graphrag"})

    def source_id(self, url_part):
        (found,) = [p for p in (self.root / "sources").glob("*.md") if url_part in p.read_text(encoding="utf-8")]
        return found.stem

    def source_text(self, ident):
        return (self.root / "sources" / f"{ident}.md").read_text(encoding="utf-8")

    def rejected(self):
        path = self.root / "_actions" / "rejected.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.is_file() else []

    def refuse(self, params, needle):
        before = self.source_text(params["source"]) if (self.root / "sources" / f"{params.get('source')}.md").is_file() else None
        with self.assertRaises(ActionError) as caught:
            run_action(self.root, "set-source", params)
        self.assertIn(needle, str(caught.exception))
        if before is not None:
            self.assertEqual(self.source_text(params["source"]), before)


class TestSetSourceCriteria(SetSourceCase):
    def test_sets_publisher_and_kind_touching_only_those_lines(self):
        ident = self.source_id("arxiv.org")
        before = self.source_text(ident)
        (record,) = run_batch(self.root, "set-source", [{"source": ident, "publisher": "Microsoft", "kind": "vendor"}])
        after = self.source_text(ident)
        self.assertEqual(record["action"], "set-source")
        diff = [(a, b) for a, b in zip(before.splitlines(), after.splitlines()) if a != b]
        self.assertEqual(diff, [('kind: "academic"', 'kind: "vendor"'), ('publisher: "arxiv-authors"', 'publisher: "Microsoft"')])
        self.assertEqual(len(before.splitlines()), len(after.splitlines()))
        self.assertEqual(self.verify(), [])

    def test_publisher_alone_and_kind_alone(self):
        ident = self.source_id("arxiv.org")
        run_action(self.root, "set-source", {"source": ident, "publisher": "Microsoft"})
        self.assertIn('publisher: "Microsoft"', self.source_text(ident))
        self.assertIn('kind: "academic"', self.source_text(ident))
        run_action(self.root, "set-source", {"source": ident, "kind": "vendor"})
        self.assertIn('kind: "vendor"', self.source_text(ident))

    def test_logged_like_every_action(self):
        ident = self.source_id("arxiv.org")
        run_action(self.root, "set-source", {"source": ident, "publisher": "Microsoft"})
        last = json.loads((self.root / "_actions" / "actions.jsonl").read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual((last["action"], last["params"]), ("set-source", {"source": ident, "publisher": "Microsoft"}))
        self.assertEqual(last["files"], [f"sources/{ident}.md"])

    def test_refusals_leave_files_and_go_to_rejected(self):
        ident = self.source_id("arxiv.org")
        claim = "graphrag"
        cases = [
            ({"source": ident}, "a publisher or a kind"),
            ({"source": "no-such-source", "publisher": "x"}, "unknown object"),
            ({"source": claim, "publisher": "x"}, "frozen-source"),
            ({"source": ident, "kind": "bogus"}, "official"),
            ({"source": ident, "publisher": "  "}, "publisher"),
            ({"source": ident, "publisher": "arxiv.org"}, "hosts or mirrors"),
            ({"source": ident, "publisher": "WWW.GitHub.com"}, "hosts or mirrors"),
            ({"source": ident, "publisher": "gist.github.com"}, "hosts or mirrors"),
            ({"publisher": "x"}, "source"),
            ({"source": ident, "publisher": "x", "title": "t"}, "unknown parameter"),
        ]
        for params, needle in cases:
            with self.subTest(params=params):
                self.refuse(params, needle)
        self.assertEqual(len(self.rejected()), len(cases))

    def test_no_change_is_refused(self):
        ident = self.source_id("arxiv.org")
        self.refuse({"source": ident, "publisher": "arxiv-authors"}, "no change")

    def test_batch_is_all_or_nothing(self):
        one, two = self.source_id("arxiv.org"), self.source_id("microsoft.github.io")
        before = (self.source_text(one), self.source_text(two))
        with self.assertRaises(ActionError):
            run_batch(self.root, "set-source", [{"source": one, "publisher": "Microsoft"}, {"source": two, "kind": "bogus"}])
        self.assertEqual((self.source_text(one), self.source_text(two)), before)
        run_batch(self.root, "set-source", [{"source": one, "publisher": "Microsoft"}, {"source": two, "publisher": "Microsoft"}])
        self.assertIn('publisher: "Microsoft"', self.source_text(two))


class TestSetSourceEffect(SetSourceCase):
    def figures(self):
        ontology, graph = load_ontology(self.root), load_graph(self.root)
        return graph_counts.claim_figures(self.root, ontology, graph)["with_2_publishers"], publisher_count(self.root, RUN, {"a1", "a2"})

    def test_same_publisher_collapses_independence(self):
        self.assertEqual(self.figures(), (1, 2))
        run_action(self.root, "set-source", {"source": self.source_id("arxiv.org"), "publisher": "Microsoft"})
        run_action(self.root, "set-source", {"source": self.source_id("microsoft.github.io"), "publisher": "microsoft"})
        self.assertEqual(self.figures(), (0, 1))

    def test_kind_first_party_removes_a_source_from_independence(self):
        run_action(self.root, "set-source", {"source": self.source_id("arxiv.org"), "kind": "first-party"})
        self.assertEqual(self.figures(), (0, 1))


if __name__ == "__main__":
    unittest.main()
