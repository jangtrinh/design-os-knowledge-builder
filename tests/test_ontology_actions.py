"""A6/A9: typed local writes — criteria, atomic edits, verify gate, byte-identical rollback, index, log."""

import hashlib
import json
import unittest

from knowledge_builder.ontology.actions import ActionError, run_action
from tests.test_ontology_support import RootCase, run_cli


def snapshot(root):
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*")) if p.is_file()
    }


class ActionCase(RootCase):
    def setUp(self):
        super().setUp()
        # cmp no longer links beta, so beta has no inbound link and can be deprecated cleanly.
        self.replace("cmp.md", '  - link_type: "compares"\n    target_id: "beta"\n', "")
        code, out, err = run_cli(["knowledge-builder", "index", "--root", str(self.root)])
        self.assertEqual(code, 0, out + err)

    def log(self):
        path = self.root / "_actions" / "actions.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def index(self):
        return {e["id"]: e for e in json.loads(self.read("index.json"))}


class TestDeprecate(ActionCase):
    def test_success_edits_indexes_and_logs(self):
        before = snapshot(self.root)
        result = run_action(self.root, "deprecate", {"target": "beta", "replacement": "alpha"})
        self.assertEqual(result["files"], ["beta.md"])
        text = self.read("beta.md")
        self.assertIn('status: "deprecated"', text)
        self.assertIn('superseded_by: "alpha"', text)
        self.assertEqual(self.index()["beta"]["status"], "deprecated")
        self.assertEqual(self.index()["beta"]["superseded_by"], "alpha")
        (line,) = self.log()
        self.assertEqual((line["action"], line["params"], line["files"]), ("deprecate", {"target": "beta", "replacement": "alpha"}, ["beta.md"]))
        self.assertEqual(line["before_sha"]["beta.md"], before["beta.md"])
        self.assertEqual(line["after_sha"]["beta.md"], snapshot(self.root)["beta.md"])
        self.assertIn("at", line)

    def test_criteria_failure_changes_nothing(self):
        before = snapshot(self.root)
        with self.assertRaises(ActionError) as caught:
            run_action(self.root, "deprecate", {"target": "cmp", "replacement": "alpha"})  # cmp is experimental
        self.assertIn("status-is", str(caught.exception))
        self.assertEqual(snapshot(self.root), before)
        self.assertEqual(self.log(), [])

    def test_missing_replacement_fails_criteria(self):
        with self.assertRaises(ActionError) as caught:
            run_action(self.root, "deprecate", {"target": "beta", "replacement": "ghost"})
        self.assertIn("unknown object", str(caught.exception))

    def test_inbound_link_makes_verify_fail_and_rolls_back(self):
        before = snapshot(self.root)
        with self.assertRaises(ActionError) as caught:
            run_action(self.root, "deprecate", {"target": "alpha", "replacement": "beta"})  # beta and cmp link alpha
        self.assertIn("verify failed", str(caught.exception))
        self.assertIn("use 'beta'", str(caught.exception))
        self.assertEqual(snapshot(self.root), before)


class TestRollback(ActionCase):
    def test_forced_verify_failure_restores_every_byte(self):
        before = snapshot(self.root)
        calls = []

        def verify(root):
            calls.append(1)
            return [] if len(calls) == 1 else ["[ERROR] forced failure in /"]

        with self.assertRaises(ActionError) as caught:
            run_action(self.root, "deprecate", {"target": "beta", "replacement": "alpha"}, verify=verify)
        self.assertIn("forced failure", str(caught.exception))
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse((self.root / "_actions").exists())

    def test_index_failure_after_write_rolls_back(self):
        (self.root / "index.json").write_text("[]", encoding="utf-8")  # stale but valid
        before = snapshot(self.root)
        from unittest.mock import patch
        with patch("knowledge_builder.ontology.actions.rebuild_index", side_effect=ActionError("index boom")):
            with self.assertRaises(ActionError):
                run_action(self.root, "deprecate", {"target": "beta", "replacement": "alpha"})
        self.assertEqual(snapshot(self.root), before)

    def test_only_new_failures_block_an_action(self):
        self.replace("alpha.md", 'description: "Demo object alpha."\n', "")  # pre-existing failure
        run_action(self.root, "deprecate", {"target": "beta", "replacement": "alpha"})
        self.assertIn('status: "deprecated"', self.read("beta.md"))


class TestOtherDefaults(ActionCase):
    def test_add_link(self):
        run_action(self.root, "add-link", {"source": "cmp", "link_type": "compares", "target": "beta"})
        self.assertIn("beta", [l["target_id"] for l in self.index()["cmp"]["links_out"]])
        self.assertEqual([l["source_id"] for l in self.index()["beta"]["links_in"]], ["cmp"])

    def test_add_link_wrong_type_rolls_back(self):
        before = snapshot(self.root)
        with self.assertRaises(ActionError):
            run_action(self.root, "add-link", {"source": "cmp", "link_type": "depends-on", "target": "beta"})
        self.assertEqual(snapshot(self.root), before)

    def test_create_object_from_default_template(self):
        params = {"id": "gamma", "object_type": "concept", "domain": "demo", "title": "Gamma", "description": "Demo gamma.",
                  "when": "demo gamma", "source": "_evidence/run-1/sources/source.txt"}
        result = run_action(self.root, "create-object", params)
        self.assertEqual(result["files"], ["gamma.md"])
        self.assertEqual(self.index()["gamma"]["object_type"], "concept")
        self.assertEqual(self.index()["gamma"]["source_count"], 1)
        code, out, err = run_cli(["knowledge-builder", "verify", str(self.root)])
        self.assertEqual(code, 0, out + err)

    def test_create_object_rejects_existing_id_and_bad_type(self):
        params = {"id": "alpha", "object_type": "concept", "domain": "demo", "title": "T", "description": "D",
                  "when": "w", "source": "_evidence/run-1/sources/source.txt"}
        with self.assertRaises(ActionError):
            run_action(self.root, "create-object", params)
        before = snapshot(self.root)
        with self.assertRaises(ActionError):
            run_action(self.root, "create-object", dict(params, id="delta", object_type="ghost"))
        self.assertEqual(snapshot(self.root), before)

    def test_promote_trust_tier_needs_verified_claims(self):
        run_action(self.root, "promote-trust-tier", {"target": "alpha", "tier": "verified"})
        self.assertEqual(self.index()["alpha"]["trust_tier"], "verified")
        self.replace("beta.md", 'quote="Alpha facts live here."', 'quote="Not in the source."')
        before = snapshot(self.root)
        with self.assertRaises(ActionError) as caught:
            run_action(self.root, "promote-trust-tier", {"target": "beta", "tier": "verified"})
        self.assertIn("claims-verified", str(caught.exception))
        self.assertEqual(snapshot(self.root), before)


class TestParametersAndSchema(ActionCase):
    def test_parameter_errors(self):
        cases = [
            ("deprecate", {"target": "beta"}, "missing parameter"),
            ("deprecate", {"target": "beta", "replacement": "alpha", "extra": "x"}, "unknown parameter"),
            ("deprecate", {"target": "ghost", "replacement": "alpha"}, "unknown object"),
            ("nope", {}, "unknown action"),
        ]
        for name, params, expect in cases:
            with self.subTest(name=name, expect=expect), self.assertRaises(ActionError) as caught:
                run_action(self.root, name, params)
            self.assertIn(expect, str(caught.exception))

    def test_legacy_root_refuses(self):
        (self.root / "ontology.yaml").unlink()
        with self.assertRaises(ActionError) as caught:
            run_action(self.root, "deprecate", {"target": "beta", "replacement": "alpha"})
        self.assertIn("ontology.yaml", str(caught.exception))

    def test_declared_action_types_replace_the_defaults(self):
        self.write("ontology.yaml", self.read("ontology.yaml") + (
            "action_types:\n"
            "  retire:\n"
            "    parameters: {target: {type: object_id}}\n"
            "    criteria: [{function: status-is, args: [target, active]}]\n"
            "    edits:\n"
            "      - {set: {object: target, key: status, value: experimental}}\n"
        ))
        run_action(self.root, "retire", {"target": "beta"})
        self.assertIn('status: "experimental"', self.read("beta.md"))
        with self.assertRaises(ActionError):
            run_action(self.root, "deprecate", {"target": "beta", "replacement": "alpha"})

    def test_remove_link_verb(self):
        self.write("ontology.yaml", self.read("ontology.yaml") + (
            "action_types:\n"
            "  unlink:\n"
            "    parameters: {source: {type: object_id}, link_type: {type: string}, target: {type: object_id}}\n"
            "    criteria: [{function: has-link, args: [source, link_type, target]}]\n"
            "    edits: [{remove-link: {object: source, link_type: link_type, target: target}}]\n"
        ))
        run_action(self.root, "unlink", {"source": "beta", "link_type": "depends-on", "target": "alpha"})
        self.assertEqual(self.index()["beta"]["links_out"], [])

    def test_cli_action_command(self):
        code, out, err = run_cli(["knowledge-builder", "action", "deprecate", "--root", str(self.root),
                                  "--param", "target=beta", "--param", "replacement=alpha"])
        self.assertEqual(code, 0, out + err)
        code, out, err = run_cli(["knowledge-builder", "action", "deprecate", "--root", str(self.root),
                                  "--param", "target=beta", "--param", "replacement=alpha"])
        self.assertEqual(code, 1)
        self.assertIn("status-is", out + err)


if __name__ == "__main__":
    unittest.main()
