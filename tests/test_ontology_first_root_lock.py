"""C-A5: every action runs under one root-wide lock; parallel actions serialize and lose nothing."""

import json
import threading
import unittest

from knowledge_builder.ontology.action_lock import root_lock
from knowledge_builder.ontology.actions import ActionError, run_action
from tests.pack_support import PackCase, add_atom, scaffold_root


class TestRootLock(PackCase):
    def setUp(self):
        super().setUp()
        scaffold_root(self.root)
        for index in range(6):
            add_atom(self.root, f"a{index}", f"page-{index}", f"Fact number {index} holds.", url=f"https://p{index}.example/x")

    def test_parallel_actions_are_serialized_and_nothing_is_lost(self):
        errors = []

        def work(index):
            try:
                run_action(self.root, "promote-claim", {"atom": f"a{index}", "kind": "official"})
            except Exception as exc:  # noqa: BLE001 - the test reports any failure
                errors.append(repr(exc))

        threads = [threading.Thread(target=work, args=(i,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        log = [json.loads(line) for line in (self.root / "_actions" / "actions.jsonl").read_text().splitlines()]
        self.assertEqual(len(log), 6)
        types = [e["object_type"] for e in json.loads(self.read("index.json"))]
        self.assertEqual((types.count("claim"), types.count("source")), (6, 6))
        self.assertEqual(self.verify(claims=True), [])

    def test_lock_excludes_a_second_holder_until_release(self):
        order = []
        ready = threading.Event()

        def first():
            with root_lock(self.root):
                order.append("first-in")
                ready.set()
                second_started.wait(1)
                threading.Event().wait(0.15)
                order.append("first-out")

        second_started = threading.Event()

        def second():
            ready.wait(1)
            second_started.set()
            with root_lock(self.root):
                order.append("second-in")

        t1, t2 = threading.Thread(target=first), threading.Thread(target=second)
        t1.start(); t2.start(); t1.join(); t2.join()
        self.assertEqual(order, ["first-in", "first-out", "second-in"])

    def test_failed_action_leaves_no_lock_artifact(self):
        before = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*"))
        with self.assertRaises(ActionError):
            run_action(self.root, "promote-claim", {"atom": "ghost", "kind": "official"})
        self.assertEqual(sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*")), before)


if __name__ == "__main__":
    unittest.main()
