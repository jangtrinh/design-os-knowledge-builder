"""H-2 / H-3: pack migrate --plan and --apply turn a UKMC.v1 pack into an ontology-first pack."""

import json
import unittest
from unittest.mock import patch

from knowledge_builder.verify import verify_root
from tests.migrate_support import (
    ALPHA, BETA, DELTA, EPSILON, KINDS, LEGACY_RUN, MigrateCase, fill_plan, migrate, sha, snapshot,
)
from tests.test_ontology_support import run_cli


class TestPlan(MigrateCase):
    def test_plan_writes_only_the_plan_and_never_touches_the_legacy_root(self):
        code, out, err = self.plan()
        self.assertEqual(code, 0, out + err)
        self.assertEqual([p.name for p in self.to.iterdir()], ["migration-plan.json"])
        self.assertEqual(snapshot(self.legacy), self.before)
        self.assertIn("migration-plan.json", out)

    def test_modules(self):
        self.plan()
        modules = {m["id"]: m for m in self.load_plan()["modules"]}
        self.assertEqual(sorted(modules), ["m-one", "m-two"])
        self.assertEqual(modules["m-one"]["object_type"], "concept")
        self.assertEqual(modules["m-one"]["when"], ["migrating"])
        self.assertEqual(modules["m-one"]["sha256"], sha((self.legacy / "m-one.md").read_bytes()))
        self.assertTrue(all(u.startswith("_evidence/mig-1/sources/") for u in modules["m-one"]["source"]))

    def test_every_distinct_anchor_gets_a_claim_id_and_an_atom(self):
        self.plan()
        plan = self.load_plan()
        anchors = plan["anchors"]
        self.assertEqual(len(anchors), 6)
        by_quote = {a["quote"]: a for a in anchors}
        self.assertEqual(by_quote[ALPHA]["atom"], "a1")
        self.assertEqual(by_quote[ALPHA]["modules"], {"m-one": 1, "m-two": 1})
        self.assertIsNone(by_quote[ALPHA]["backfill"])
        self.assertEqual(len({a["claim_id"] for a in anchors}), 6)
        epsilon = by_quote[EPSILON]
        self.assertTrue(epsilon["atom"].startswith("bf-"))
        self.assertEqual(epsilon["backfill"]["claim_type"], "FAILURE_MODE")
        self.assertEqual(epsilon["backfill"]["statement"], EPSILON)
        self.assertEqual(by_quote[BETA]["atom"], "a4")

    def test_sources_carry_urls_publishers_and_kind_placeholders(self):
        self.plan()
        sources = {s["legacy_uri"].rsplit("/", 1)[1]: s for s in self.load_plan()["sources"]}
        self.assertEqual(sorted(sources), sorted(KINDS))
        self.assertTrue(all(s["kind"] == "NEEDS_KIND" for s in sources.values()))
        self.assertEqual(sources["vendor-a.txt"]["publisher"], "docs.vendor.example")
        self.assertEqual(sources["vendor-a.txt"]["url"], "https://docs.vendor.example/a")
        self.assertEqual(sources["paper-b.txt"]["publisher"], "NEEDS_PUBLISHER")  # arxiv.org hosts other people's work
        self.assertEqual(sources["local-run.txt"]["url"], "local-execution")
        self.assertEqual(sources["local-run.txt"]["publisher"], "local")
        self.assertEqual(sources["vendor-a.txt"]["evidence_uri"], "_evidence/mig-1/sources/vendor-a.txt")
        self.assertEqual(sources["vendor-a.txt"]["sha256"], sha((self.legacy / "_evidence" / LEGACY_RUN / "sources" / "vendor-a.txt").read_bytes()))
        self.assertFalse(sources["unused.txt"]["used"])
        self.assertTrue(sources["vendor-a.txt"]["used"])

    def test_a_contradiction_without_its_partner_is_a_placeholder(self):
        self.plan()
        plan = self.load_plan()
        self.assertEqual(plan["contradictions"], [{"atom": "a4", "contradicts": "NEEDS_CONTRADICTS", "resolution": "scope difference: documented disagreement"}])
        self.assertEqual(plan["required_claim_ids"], ["c-alpha", "c-gamma"])

    def test_plan_refuses_instead_of_overwriting_a_plan_being_edited(self):
        self.plan()
        self.plan_path.write_text('{"mine": true}')
        code, _out, err = self.plan()
        self.assertEqual(code, 1)
        self.assertIn("already exists", err)
        self.assertEqual(json.loads(self.plan_path.read_text()), {"mine": True})

    def test_plan_refuses_a_target_that_is_not_empty(self):
        self.to.mkdir()
        (self.to / "keep.txt").write_text("mine")
        code, _out, err = self.plan()
        self.assertEqual(code, 1)
        self.assertIn("not empty", err)
        self.assertEqual([p.name for p in self.to.iterdir()], ["keep.txt"])

    def test_plan_refuses_a_root_that_is_already_an_ontology_pack(self):
        (self.legacy / "ontology.yaml").write_text('version: "1"\n')
        code, _out, err = self.plan()
        self.assertEqual(code, 1)
        self.assertIn("already has ontology.yaml", err)
        self.assertFalse(self.to.exists())

    def test_plan_refuses_a_missing_legacy_root(self):
        code, _out, err = migrate("--from", str(self.legacy / "absent"), "--to", str(self.to), "--run", "r", "--plan")
        self.assertEqual(code, 1)
        self.assertIn("not a directory", err)

    def test_plan_and_apply_are_exclusive(self):
        self.assertEqual(migrate("--from", str(self.legacy), "--to", str(self.to), "--run", "r")[0], 1)
        self.assertEqual(migrate("--from", str(self.legacy), "--to", str(self.to), "--run", "r", "--plan", "--apply", "x")[0], 1)


class TestApplyRefusals(MigrateCase):
    def test_apply_lists_every_placeholder_and_writes_nothing(self):
        self.plan()
        before = snapshot(self.to)
        code, _out, err = self.apply()
        self.assertEqual(code, 1)
        for text in ("NEEDS_KIND", "NEEDS_PUBLISHER", "NEEDS_CONTRADICTS", "vendor-a.txt", "paper-b.txt", "a4"):
            self.assertIn(text, err)
        self.assertEqual(snapshot(self.to), before)

    def test_apply_refuses_an_unknown_kind(self):
        plan = self.filled()
        plan["sources"][0]["kind"] = "blog"
        self.save_plan(plan)
        before = snapshot(self.to)
        code, _out, err = self.apply()
        self.assertEqual(code, 1)
        self.assertIn("blog", err)
        self.assertEqual(snapshot(self.to), before)

    def test_apply_refuses_two_kinds_for_one_url(self):
        plan = self.filled()
        twin = dict(plan["sources"][0], legacy_uri=plan["sources"][0]["legacy_uri"] + ".copy", evidence_uri=plan["sources"][0]["evidence_uri"] + ".copy", kind="vendor")
        plan["sources"].append(twin)
        self.save_plan(plan)
        code, _out, err = self.apply()
        self.assertEqual(code, 1)
        self.assertIn("two kinds", err)

    def test_apply_refuses_duplicate_or_malformed_claim_ids(self):
        plan = self.filled()
        plan["anchors"][1]["claim_id"] = plan["anchors"][0]["claim_id"]
        self.save_plan(plan)
        self.assertIn("twice", self.apply()[2])
        plan["anchors"][1]["claim_id"] = "Not Kebab"
        self.save_plan(plan)
        self.assertIn("kebab", self.apply()[2])

    def test_apply_refuses_when_the_legacy_root_changed_after_the_plan(self):
        self.filled()
        (self.legacy / "m-one.md").write_text((self.legacy / "m-one.md").read_text() + "\nlate edit\n")
        code, _out, err = self.apply()
        self.assertEqual(code, 1)
        self.assertIn("changed since the plan", err)

    def test_apply_needs_a_new_target(self):
        self.filled()
        (self.to / "extra.txt").write_text("x")
        code, _out, err = self.apply()
        self.assertEqual(code, 1)
        self.assertIn("not empty", err)

    def test_a_document_id_cannot_double_as_a_claim_id(self):
        plan = self.filled()
        plan["anchors"][0]["claim_id"] = "m-one"
        self.save_plan(plan)
        code, _out, err = self.apply()
        self.assertEqual(code, 1)
        self.assertIn("twice", err)

    def test_a_failed_apply_leaves_only_the_plan(self):
        from knowledge_builder.ontology.actions import ActionError, run_action

        self.filled()

        def flaky(root, name, params, *rest):
            if name == "create-object":
                raise ActionError("boom")
            return run_action(root, name, params, *rest)

        with patch("knowledge_builder.pack.migrate_apply.run_action", flaky):
            code, _out, err = self.apply()
        self.assertEqual(code, 1, err)
        self.assertIn("boom", err)
        self.assertEqual([p.name for p in self.to.iterdir()], ["migration-plan.json"])
        self.assertEqual(snapshot(self.legacy), self.before)


class TestApply(MigrateCase):
    def setUp(self):
        super().setUp()
        self.filled()
        self.code, self.out, self.err = self.apply()

    def ledger(self):
        path = self.to / "_evidence" / "mig-1" / "evidence.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

    def actions(self):
        lines = (self.to / "_actions" / "actions.jsonl").read_text().splitlines()
        return [json.loads(line)["action"] for line in lines if line.strip()]

    def test_apply_succeeds_and_pack_check_passes(self):
        self.assertEqual(self.code, 0, self.out + self.err)
        self.assertIn("failures: 0", self.out)
        self.assertEqual(verify_root(self.to, claims=True)[2], [])
        code, out, err = run_cli(["knowledge-builder", "pack", "check", "--root", str(self.to)])
        self.assertEqual(code, 0, out + err)

    def test_the_legacy_root_is_byte_identical(self):
        self.assertEqual(snapshot(self.legacy), self.before)

    def test_captures_are_copied_byte_for_byte(self):
        old = self.legacy / "_evidence" / LEGACY_RUN / "sources"
        new = self.to / "_evidence" / "mig-1" / "sources"
        self.assertEqual(snapshot(old), snapshot(new))

    def test_legacy_atoms_are_re_recorded_and_anchors_without_an_atom_are_backfilled(self):
        atoms = {a["id"]: a for a in self.ledger()}
        legacy = [a for a in atoms.values() if a["metadata"].get("v1_atom")]
        self.assertEqual(sorted(a["id"] for a in legacy), ["a1", "a2", "a3", "a4", "a5", "a6"])
        self.assertTrue(all(a["run_id"] == "mig-1" and a["source_uri"].startswith("_evidence/mig-1/sources/") for a in atoms.values()))
        backfill = [a for a in atoms.values() if a["metadata"].get("backfill") is True]
        self.assertEqual(len(backfill), 1)
        self.assertEqual((backfill[0]["quote"], backfill[0]["claim_type"]), (EPSILON, "FAILURE_MODE"))
        self.assertEqual(atoms["a4"]["metadata"]["contradicts"], "a1")

    def test_one_claim_per_distinct_anchor_and_a_source_per_used_url(self):
        self.assertEqual(len(self.names("claims")), 6)
        self.assertEqual(len(self.names("sources")), 3)
        self.assertEqual(sorted(p.name for p in self.to.glob("*.md")), ["m-one.md", "m-two.md"])
        sources = "".join((self.to / "sources" / n).read_text() for n in self.names("sources"))
        self.assertIn('kind: "first-party"', sources)
        self.assertIn('publisher: "Test Authors"', sources)
        self.assertIn('publisher: "docs.vendor.example"', sources)

    def test_every_write_went_through_the_action_pipeline(self):
        actions = self.actions()
        self.assertEqual(actions.count("promote-claim"), 6)
        self.assertEqual(actions.count("create-object"), 2)
        self.assertEqual(actions.count("add-link"), 7)  # m-one cites 4 claims, m-two cites 3
        self.assertEqual(actions.count("resolve-contradiction"), 1)

    def test_bodies_are_ported_with_claim_anchors_and_cites_links(self):
        one, two = (self.to / "m-one.md").read_text(), (self.to / "m-two.md").read_text()
        self.assertNotIn("ease:source", one + two)
        self.assertEqual(one.count("<!-- ease:claim id="), 4)
        self.assertEqual(two.count("<!-- ease:claim id="), 3)
        self.assertIn(ALPHA, one)
        self.assertIn("  <!-- ease:claim id=", one)  # the indented anchor under Failure Modes keeps its indent
        self.assertEqual(one.count('link_type: "cites"'), 4)
        self.assertIn('title: "Module m-one"', one)
        self.assertIn('  - "migrating"', one)

    def test_the_contradiction_is_linked_and_resolved(self):
        beta = next(p for p in (self.to / "claims").glob("*.md") if BETA in p.read_text() and 'claim_type: "CONTRADICTION"' in p.read_text())
        text = beta.read_text()
        self.assertIn('resolution: "scope difference: documented disagreement"', text)
        self.assertIn('link_type: "contradicts"', text)

    def test_the_run_keeps_the_legacy_criteria(self):
        state = json.loads((self.to / "_evidence" / "mig-1" / "state.json").read_text())
        self.assertEqual(state["required_claim_ids"], ["c-alpha", "c-gamma"])
        self.assertEqual((state["budget_total"], state["researcher_runtime"]), (50, "r-model"))
        self.assertEqual(json.loads((self.to / "pack.json").read_text())["run"], "mig-1")

    def test_the_plan_stays_as_the_audit_trail(self):
        self.assertTrue(self.plan_path.is_file())

    def test_a_second_apply_is_refused(self):
        code, _out, err = self.apply()
        self.assertEqual(code, 1)
        self.assertIn("not empty", err)


class TestEdges(MigrateCase):
    def edit_ledger(self, change):
        path = self.legacy / "_evidence" / LEGACY_RUN / "evidence.jsonl"
        atoms = [json.loads(line) for line in path.read_text().splitlines()]
        change(atoms)
        path.write_text("".join(json.dumps(a) + "\n" for a in atoms))
        self.before = snapshot(self.legacy)

    def test_a_root_with_no_evidence_is_refused(self):
        import shutil

        shutil.rmtree(self.legacy / "_evidence")
        code, _out, err = self.plan()
        self.assertEqual(code, 1)
        self.assertIn("nothing to migrate", err)
        self.assertFalse(self.to.exists())

    def test_an_anchor_that_cites_no_capture_is_listed_and_nothing_is_written(self):
        text = (self.legacy / "m-two.md").read_text().replace("sources/local-run.txt", "sources/elsewhere.txt")
        (self.legacy / "m-two.md").write_text(text)
        code, _out, err = self.plan()
        self.assertEqual(code, 1)
        self.assertIn("m-two.md", err)
        self.assertIn("elsewhere.txt", err)
        self.assertFalse(self.to.exists())

    def test_a_contradiction_partner_without_an_anchor_becomes_a_claim(self):
        self.edit_ledger(lambda atoms: atoms[3]["metadata"].update(contradicts="a5"))
        self.plan()
        plan = self.load_plan()
        self.assertEqual(plan["contradictions"][0]["contradicts"], "a5")
        self.assertTrue(next(s for s in plan["sources"] if s["legacy_uri"].endswith("unused.txt"))["used"])
        fill_plan(self.plan_path)
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(len(self.names("claims")), 7)

    def test_atoms_outside_the_captures_are_listed_not_dropped_silently(self):
        self.edit_ledger(lambda atoms: atoms[4].update(source_uri="_evidence/leg-1/sources/gone.txt"))
        self.plan()
        self.assertEqual([s["atom"] for s in self.load_plan()["skipped_atoms"]], ["a5"])

    def test_atom_ids_repeated_across_runs_are_refused(self):
        import shutil

        shutil.copytree(self.legacy / "_evidence" / LEGACY_RUN, self.legacy / "_evidence" / "leg-2")
        code, _out, err = self.plan()
        self.assertEqual(code, 1)
        self.assertIn("unique across", err)

    def test_a_ledger_edited_after_the_plan_is_noticed(self):
        self.filled()
        self.edit_ledger(lambda atoms: atoms[0].update(statement="Changed."))
        code, _out, err = self.apply()
        self.assertEqual(code, 1)
        self.assertIn("evidence.jsonl", err)

    def test_apply_checks_from_and_run_against_the_plan(self):
        self.filled()
        self.assertIn("--run other", migrate("--to", str(self.to), "--apply", str(self.plan_path), "--run", "other")[2])
        self.assertIn("--from", migrate("--to", str(self.to), "--apply", str(self.plan_path), "--from", str(self.to))[2])

    def test_a_cited_capture_with_no_url_needs_one_unless_it_is_first_party(self):
        self.filled()
        plan = self.load_plan()
        local = next(s for s in plan["sources"] if s["legacy_uri"].endswith("local-run.txt"))
        local["url"], local["kind"] = None, "official"
        self.save_plan(plan)
        code, _out, err = self.apply()
        self.assertEqual(code, 1)
        self.assertIn("NEEDS_URL", err)

    def test_topic_defaults_to_the_legacy_folder_and_can_be_set(self):
        self.plan()
        self.assertEqual(self.load_plan()["topic"], "legacy")
        self.plan_path.unlink()
        migrate("--from", str(self.legacy), "--to", str(self.to), "--run", "mig-1", "--plan", "--topic", "My topic")
        self.assertEqual(self.load_plan()["topic"], "My topic")


if __name__ == "__main__":
    unittest.main()
