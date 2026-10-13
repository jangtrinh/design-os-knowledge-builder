"""promote-claim never names a publisher after a hosting or mirror host; pack status/check warn on a publisher seen under two kinds."""

import json
import unittest

from knowledge_builder.ontology.actions import ActionError, run_action
from tests.pack_support import PackCase, add_atom, scaffold_root
from tests.test_pack_commands import PackInitCase, pack

HOSTS = [
    "https://web.archive.org/web/2026/https://x.example/a", "https://raw.githubusercontent.com/o/r/main/a.md",
    "https://github.com/o/r/blob/main/a.md", "https://gist.githubusercontent.com/o/abc", "https://arxiv.org/abs/2404.16130",
    "https://www.arxiv.org/abs/2404.16130", "https://export.arxiv.org/abs/1", "https://hackmd.io/@o/note",
]


class TestHostingHosts(PackCase):
    def setUp(self):
        super().setUp()
        scaffold_root(self.root)

    def test_a_hosting_host_cannot_name_the_publisher(self):
        for number, url in enumerate(HOSTS):
            with self.subTest(url=url):
                add_atom(self.root, f"h{number}", f"h{number}", f"Body {number}.", url=url)
                with self.assertRaises(ActionError) as caught:
                    run_action(self.root, "promote-claim", {"atom": f"h{number}", "kind": "academic"})
                self.assertIn("publisher", str(caught.exception))
                self.assertIn("--param publisher=", str(caught.exception))
        self.assertEqual(list((self.root / "sources").glob("*.md")), [])

    def test_an_explicit_publisher_is_accepted(self):
        add_atom(self.root, "a1", "a1", "Body.", url="https://arxiv.org/abs/2404.16130")
        run_action(self.root, "promote-claim", {"atom": "a1", "kind": "academic", "publisher": "microsoft.com"})
        (source,) = (self.root / "sources").glob("*.md")
        self.assertIn('publisher: "microsoft.com"', source.read_text(encoding="utf-8"))

    def test_other_hosts_still_default_to_their_own_host(self):
        for url, publisher in [("https://en.wikipedia.org/wiki/X", "en.wikipedia.org"), ("https://microsoft.github.io/graphrag/", "microsoft.github.io"),
                               ("https://notgithub.com/x", "notgithub.com")]:
            with self.subTest(url=url):
                add_atom(self.root, f"w-{publisher}", publisher.replace(".", "-"), f"Body {publisher}.", url=url)
                run_action(self.root, "promote-claim", {"atom": f"w-{publisher}", "kind": "official"})
                self.assertTrue(any(f'publisher: "{publisher}"' in p.read_text(encoding="utf-8") for p in (self.root / "sources").glob("*.md")))


class TestPublisherKindWarning(PackInitCase):
    def setUp(self):
        super().setUp()
        self.init()
        self.add_atoms()

    def promote(self, atom, kind, publisher):
        run_action(self.root, "promote-claim", {"atom": atom, "kind": kind, "publisher": publisher})

    def test_a_publisher_under_two_kinds_is_reported_and_check_still_passes(self):
        self.promote("a1", "official", "Acme.example")
        self.promote("a2", "vendor", "acme.example")
        code, out, err = pack("status", "--root", str(self.root), "--json")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(json.loads(out)["publisher_kind_conflicts"], [{"publisher": "acme.example", "kinds": ["official", "vendor"]}])
        code, out, err = pack("status", "--root", str(self.root))
        self.assertIn("warning: publisher acme.example appears as official, vendor", out)
        code, out, err = pack("check", "--root", str(self.root))
        self.assertEqual(code, 0, out + err)
        self.assertIn("warning: publisher acme.example appears as official, vendor", out)
        self.assertIn("failures: 0", out)

    def test_consistent_kinds_print_no_warning(self):
        self.promote("a1", "official", "acme.example")
        self.promote("a2", "official", "acme.example")
        code, out, _err = pack("status", "--root", str(self.root), "--json")
        self.assertEqual(json.loads(out)["publisher_kind_conflicts"], [])
        self.assertNotIn("warning", pack("check", "--root", str(self.root))[1])


if __name__ == "__main__":
    unittest.main()
