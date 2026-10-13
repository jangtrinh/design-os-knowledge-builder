"""Fix round 1: publisher independence for the gate, templates inside the package, claim id slugs."""

import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from knowledge_builder.ontology.actions import run_action
from knowledge_builder.ontology.claim_state import slug
from knowledge_builder.research.ledger_gate import ledger_evaluation_input
from tests.pack_support import PackCase, add_atom, scaffold_root
from tests.test_ontology_support import FIXTURE, make_stop_run

REPO = Path(__file__).resolve().parent.parent


class TestGatePublisherIndependence(PackCase):
    def setUp(self):
        super().setUp()
        scaffold_root(self.root)

    def count(self):
        return ledger_evaluation_input(self.root, "r1").independent_sources_count

    def promote(self, atom):
        run_action(self.root, "promote-claim", {"atom": atom, "kind": "official"})

    def test_two_captures_from_one_publisher_count_once(self):
        add_atom(self.root, "a1", "p1", "One fact.", url="https://same.example/a")
        add_atom(self.root, "a2", "p2", "Two fact.", url="https://same.example/b")  # different file, same publisher
        self.promote("a1"); self.promote("a2")
        self.assertEqual(self.count(), 1)

    def test_a_second_publisher_counts_as_two(self):
        add_atom(self.root, "a1", "p1", "One fact.", url="https://same.example/a")
        add_atom(self.root, "a2", "p2", "Two fact.", url="https://same.example/b")
        add_atom(self.root, "a3", "p3", "Three fact.", url="https://other.example/c")
        for atom in ("a1", "a2", "a3"):
            self.promote(atom)
        self.assertEqual(self.count(), 2)

    def test_atoms_not_promoted_to_a_source_do_not_count(self):
        add_atom(self.root, "a1", "p1", "One fact.", url="https://same.example/a")
        add_atom(self.root, "a2", "p2", "Two fact.", url="https://other.example/b")
        self.promote("a1")
        self.assertEqual(self.count(), 1)

    def test_publisher_names_compare_case_insensitively(self):
        add_atom(self.root, "a1", "p1", "One fact.", url="https://x.example/a")
        add_atom(self.root, "a2", "p2", "Two fact.", url="https://y.example/b")
        run_action(self.root, "promote-claim", {"atom": "a1", "kind": "official", "publisher": "Acme"})
        run_action(self.root, "promote-claim", {"atom": "a2", "kind": "official", "publisher": "ACME"})
        self.assertEqual(self.count(), 1)

    def test_ontology_root_without_a_source_type_and_legacy_roots_keep_the_inode_count(self):
        for legacy in (False, True):
            root = Path(self._tmp.name) / f"inode-{legacy}"
            shutil.copytree(FIXTURE, root)
            if legacy:
                (root / "ontology.yaml").unlink()
            make_stop_run(root, "run-1")
            self.assertEqual(ledger_evaluation_input(root, "run-1").independent_sources_count, 2, legacy)


class TestSlug(unittest.TestCase):
    def test_cut_at_a_word_boundary_within_the_limit(self):
        result = slug("abcdefg " * 10, 60)
        self.assertEqual(result, "-".join(["abcdefg"] * 7))
        self.assertLessEqual(len(result), 60)

    def test_never_ends_with_a_hyphen_and_short_text_is_untouched(self):
        self.assertFalse(slug("a" * 59 + " tail", 60).endswith("-"))
        self.assertEqual(slug("Short statement.", 60), "short-statement")

    def test_one_overlong_word_is_hard_cut(self):
        self.assertEqual(slug("x" * 80, 60), "x" * 60)


class TestPackaging(unittest.TestCase):
    def test_templates_live_in_the_package_and_load_through_importlib_resources(self):
        from importlib.resources import files

        base = files("knowledge_builder") / "templates"
        self.assertTrue((base / "ontology.starter.yaml").is_file())
        self.assertTrue((base / "_templates" / "claim.md.tmpl").is_file())
        self.assertFalse((REPO / "templates").exists())

    def test_built_wheel_contains_the_starter_and_every_template(self):
        with tempfile.TemporaryDirectory() as out:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "-w", out, str(REPO)],
                capture_output=True, text=True,
            )
            if result.returncode != 0:  # no setuptools in this interpreter: let uv build in isolation
                result = subprocess.run(["uv", "build", "--wheel", "--out-dir", out, str(REPO)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            (wheel,) = Path(out).glob("*.whl")
            names = set(zipfile.ZipFile(wheel).namelist())
        want = {"knowledge_builder/templates/ontology.starter.yaml"} | {
            f"knowledge_builder/templates/_templates/{k}.md.tmpl" for k in ("concept", "guide", "comparison", "decision-record", "claim", "source")
        }
        self.assertEqual(want - names, set())


if __name__ == "__main__":
    unittest.main()
