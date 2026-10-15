"""Action write boundary: creation paths, rollback under write failure, failure multiplicity, log truncation."""

import errno
import hashlib
import json
import os
import unittest
from unittest.mock import patch

from knowledge_builder.containment import atomic_write as real_atomic_write
from knowledge_builder.ontology.action_edits import EditError, add_link, set_key
from knowledge_builder.ontology.actions import ActionError, run_action
from tests.test_ontology_support import RootCase, make_stop_run, run_cli


REJECTED_TRACE = "_actions/rejected.jsonl"


def snapshot(root):
    """Every file's sha256, except the one trace a refused action may add: _actions/rejected.jsonl."""
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*")) if p.is_file() and p.relative_to(root).as_posix() != REJECTED_TRACE
    }


MAKE = (
    "action_types:\n"
    "  make:\n"
    "    parameters: {name: {type: string}, source: {type: string}}\n"
    "    edits:\n"
    "      - create-object: {id: \"$name\", object_type: concept, values: {title: T, domain: demo, description: D, when: w, source: \"$source\"}}\n"
)
TWO = (
    "action_types:\n"
    "  two:\n"
    "    parameters: {a: {type: object_id}, b: {type: object_id}}\n"
    "    edits:\n"
    "      - {set: {object: a, key: status, value: experimental}}\n"
    "      - {set: {object: b, key: status, value: experimental}}\n"
)
SOURCE = "_evidence/run-1/sources/source.txt"


class WriteCase(RootCase):
    def setUp(self):
        super().setUp()
        run_cli(["knowledge-builder", "index", "--root", str(self.root)])


class TestCreationPath(WriteCase):
    def test_declared_string_id_cannot_leave_the_root(self):
        self.write("ontology.yaml", self.read("ontology.yaml") + MAKE)
        before = snapshot(self.root)
        outside = self.root.parent / "outside.md"
        for bad in ("../outside", "sub/escape", "/tmp/abs", "Upper", ".hidden"):
            with self.subTest(bad), self.assertRaises(ActionError):
                run_action(self.root, "make", {"name": bad, "source": SOURCE})
        self.assertFalse(outside.exists())
        self.assertEqual(snapshot(self.root), before)

    def test_declared_string_id_that_is_valid_still_works(self):
        self.write("ontology.yaml", self.read("ontology.yaml") + MAKE)
        run_action(self.root, "make", {"name": "fresh-one", "source": SOURCE})
        self.assertTrue((self.root / "fresh-one.md").is_file())


class TestRollbackUnderWriteFailure(WriteCase):
    def test_persistent_write_failure_after_first_file_restores_all_bytes(self):
        self.write("ontology.yaml", self.read("ontology.yaml") + TWO)
        before = snapshot(self.root)
        calls = []

        def failing(directory, name, data):
            calls.append(name)
            if len(calls) > 1:
                raise OSError(errno.ENOSPC, "no space left on device")
            return real_atomic_write(directory, name, data)

        with patch("knowledge_builder.ontology.actions.atomic_write", failing):
            with self.assertRaises(OSError):
                run_action(self.root, "two", {"a": "alpha", "b": "beta"})
        self.assertGreater(len(calls), 1)
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse((self.root / "_actions").exists())

    def test_index_write_failure_restores_the_old_index(self):
        before = snapshot(self.root)
        with patch("knowledge_builder.index.atomic_write", side_effect=OSError(errno.ENOSPC, "full")):
            with self.assertRaises((ActionError, OSError)):
                run_action(self.root, "deprecate", {"target": "beta", "replacement": "alpha"})
        self.assertEqual(snapshot(self.root), before)


class TestFailureMultiplicity(WriteCase):
    def test_duplicate_of_an_existing_failure_text_is_still_new(self):
        solo = self.read("alpha.md").replace('"alpha"', '"solo"').replace('description: "Demo object solo."\n', "")
        solo = solo.replace('description: "Demo object alpha."\n', "")
        self.write("solo.md", solo)
        self.write("ontology.yaml", self.read("ontology.yaml").replace(
            "  comparison:\n    implements: [sourced-document]\n",
            "  comparison:\n    implements: [sourced-document]\n    properties:\n      - {name: description, type: string, required: true}\n",
        ) + (
            "action_types:\n  retype:\n    parameters: {target: {type: object_id}}\n"
            "    edits: [{set: {object: target, key: object_type, value: comparison}}]\n"
        ))
        run_cli(["knowledge-builder", "index", "--root", str(self.root)])
        before = snapshot(self.root)
        with self.assertRaises(ActionError):
            run_action(self.root, "retype", {"target": "solo"})
        self.assertEqual(snapshot(self.root), before)


class TestLogAppend(WriteCase):
    def test_partial_append_is_truncated_and_action_rolled_back(self):
        self.replace("cmp.md", '  - link_type: "compares"\n    target_id: "beta"\n', "")
        run_cli(["knowledge-builder", "index", "--root", str(self.root)])
        run_action(self.root, "deprecate", {"target": "beta", "replacement": "alpha"})
        log = self.root / "_actions" / "actions.jsonl"
        good = log.read_bytes()
        make_stop_run(self.root)
        before = snapshot(self.root)

        def partial(fd, data):
            os.write(fd, data[:10])
            raise OSError(errno.EIO, "disk error")

        with patch("knowledge_builder.ontology.action_log.write_all", partial):
            with self.assertRaises(OSError):
                run_action(self.root, "promote-trust-tier", {"target": "alpha", "tier": "verified"})
        self.assertEqual(log.read_bytes(), good)
        json.loads(good.decode().splitlines()[-1])
        self.assertEqual(snapshot(self.root), before)


class TestDuplicateKeys(unittest.TestCase):
    DOC = '---\nid: "a"\nstatus: "active"\nstatus: "active"\n---\nbody\n'

    def test_edits_refuse_ambiguous_frontmatter(self):
        with self.assertRaises(EditError):
            set_key(self.DOC, "status", "deprecated")
        with self.assertRaises(EditError):
            add_link('---\nid: "a"\nlink_types: []\nlink_types: []\n---\n', "x", "y")


if __name__ == "__main__":
    unittest.main()
