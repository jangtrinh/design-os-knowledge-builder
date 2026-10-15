"""F-2 rejected actions leave a trace, F-3 query refuses unknown ids, F-5 default actions take --batch."""

import json
import unittest

from knowledge_builder.ontology.actions import ActionError, run_action, run_batch
from tests.test_ontology_actions import REJECTED_TRACE, ActionCase, snapshot
from tests.test_ontology_support import RootCase, run_cli
from tests.test_pack_commands import PackInitCase, pack

REJECTED = REJECTED_TRACE
BAD = {"target": "beta", "replacement": "nobody"}


def changed(root, before):
    """Files whose bytes differ from `before`, counting rejected.jsonl (which `snapshot` leaves out)."""
    after = {**snapshot(root), **({REJECTED: "present"} if (root / REJECTED).exists() else {})}
    return {k for k in after if before.get(k) != after[k]}


class TestRejectedTrace(ActionCase):
    def rejected(self):
        path = self.root / REJECTED
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def test_rejected_action_appends_one_line_and_changes_nothing_else(self):
        before = snapshot(self.root)
        with self.assertRaises(ActionError):
            run_action(self.root, "deprecate", BAD)
        self.assertEqual(changed(self.root, before), {REJECTED})
        (line,) = self.rejected()
        self.assertEqual((line["action"], line["params"]), ("deprecate", BAD))
        self.assertIn("nobody", line["reason"])
        self.assertTrue(line["at"])
        self.assertEqual(self.log(), [])

    def test_every_rejection_appends(self):
        for name in ("deprecate", "no-such-action"):
            with self.assertRaises(ActionError):
                run_action(self.root, name, BAD)
        self.assertEqual([r["action"] for r in self.rejected()], ["deprecate", "no-such-action"])

    def test_success_writes_no_rejected_file(self):
        run_action(self.root, "deprecate", {"target": "beta", "replacement": "alpha"})
        self.assertFalse((self.root / REJECTED).exists())

    def test_batch_rejection_is_one_line_with_all_items(self):
        items = [{"source": "cmp", "link_type": "compares", "target": "beta"}, {"source": "cmp", "link_type": "compares", "target": "nobody"}]
        with self.assertRaises(ActionError):
            run_batch(self.root, "add-link", items)
        (line,) = self.rejected()
        self.assertEqual(line["params"], items)

    def test_legacy_root_is_left_alone(self):
        (self.root / "ontology.yaml").unlink()
        before = snapshot(self.root)
        with self.assertRaises(ActionError):
            run_action(self.root, "deprecate", BAD)
        self.assertEqual(snapshot(self.root), before)


class TestStatusShowsRejected(PackInitCase):
    def test_count_in_json_and_text(self):
        self.init()
        with self.assertRaises(ActionError):
            run_action(self.root, "promote-claim", {"atom": "ghost", "kind": "official"})
        code, out, err = pack("status", "--root", str(self.root), "--json")
        self.assertEqual((code, json.loads(out)["rejected_actions"]), (0, 1), out + err)
        self.assertIn("rejected actions: 1", pack("status", "--root", str(self.root))[1])


class TestQueryUnknownIds(RootCase):
    def setUp(self):
        super().setUp()
        code, out, err = run_cli(["knowledge-builder", "index", "--root", str(self.root)])
        self.assertEqual(code, 0, out + err)

    def query(self, *args):
        code, out, err = run_cli(["knowledge-builder", "query", "--root", str(self.root), *args])
        return code, out + err

    def test_unknown_ids_exit_1_naming_them(self):
        for args, needle in [(("--linked-to", "nobody"), "unknown object 'nobody'"),
                             (("--implements", "ghost-iface"), "unknown interface 'ghost-iface'"),
                             (("--object-type", "ghost-type"), "unknown object type 'ghost-type'")]:
            with self.subTest(args=args):
                code, text = self.query(*args)
                self.assertEqual(code, 1)
                self.assertIn(needle, text)

    def test_a_real_object_with_no_match_is_still_an_empty_list(self):
        code, text = self.query("--linked-to", "alpha", "--status", "deprecated")
        self.assertEqual((code, json.loads(text)), (0, []))


class TestAddLinkBatch(ActionCase):
    ITEMS = [{"source": "cmp", "link_type": "compares", "target": "beta"}, {"source": "alpha", "link_type": "depends-on", "target": "beta"}]

    def test_two_links_one_verify_one_log_line_each(self):
        calls = []
        records = run_batch(self.root, "add-link", self.ITEMS, verify=lambda root: calls.append(1) or [])
        self.assertEqual(len(calls), 2)  # baseline + after, regardless of item count
        self.assertEqual([r["params"] for r in records], self.ITEMS)
        self.assertEqual(len(self.log()), 2)
        self.assertIn('target_id: "beta"', self.read("alpha.md"))
        self.assertIn('target_id: "beta"', self.read("cmp.md"))

    def test_all_or_nothing(self):
        before = snapshot(self.root)
        bad = [*self.ITEMS, {"source": "alpha", "link_type": "depends-on", "target": "nobody"}]
        with self.assertRaises(ActionError):
            run_batch(self.root, "add-link", bad)
        self.assertEqual(changed(self.root, before), {REJECTED})

    def test_cli_batch_file(self):
        path = self.root.parent / "links.jsonl"
        path.write_text("".join(json.dumps(i) + "\n" for i in self.ITEMS), encoding="utf-8")
        code, out, err = run_cli(["knowledge-builder", "action", "add-link", "--root", str(self.root), "--batch", str(path)])
        self.assertEqual(code, 0, out + err)
        self.assertIn("2 item(s)", out)

    def test_create_object_still_takes_no_batch(self):
        with self.assertRaises(ActionError) as caught:
            run_batch(self.root, "create-object", [{}, {}])
        self.assertIn("batch", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
