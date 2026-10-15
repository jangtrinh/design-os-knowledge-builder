"""H-1: ontology is the default. A root without ontology.yaml is refused unless --legacy is passed."""

import shutil
import unittest

from tests.pack_support import PackCase
from tests.test_ontology_support import FIXTURE, run_cli

MESSAGE = (
    "no ontology.yaml: run `pack init` for a new pack or `pack migrate` for an existing one; "
    "pass --legacy to check a UKMC.v1 root"
)
WARNING = "[WARN] no ontology.yaml: legacy mode, UKMC.v1 checks only\n"


class TestOntologyIsTheDefault(PackCase):
    def legacy(self):
        shutil.copytree(FIXTURE, self.root)
        (self.root / "ontology.yaml").unlink()

    def cli(self, *args):
        return run_cli(["knowledge-builder", *args])

    def assertRefused(self, result):
        code, out, err = result
        self.assertEqual(code, 1, out + err)
        self.assertIn(MESSAGE, err)
        self.assertEqual(out, "")

    def test_every_root_command_refuses_a_legacy_root(self):
        self.legacy()
        root = str(self.root)
        for argv in (
            ("verify", root),
            ("verify", root, "--claims"),
            ("index", "--root", root),
            ("query", "--root", root),
            ("action", "create-object", "--root", root, "--param", "id=x"),
            ("pack", "status", "--root", root),
            ("pack", "check", "--root", root),
            ("gate", "--root", root, "--run-id", "ontology-261013"),
        ):
            with self.subTest(argv=argv):
                self.assertRefused(self.cli(*argv))

    def test_refusal_writes_nothing(self):
        self.legacy()
        before = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*"))
        self.cli("index", "--root", str(self.root))
        self.cli("action", "create-object", "--root", str(self.root), "--param", "id=x")
        after = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*"))
        self.assertEqual(before, after)

    def test_legacy_flag_restores_verify_and_index(self):
        self.legacy()
        self.assertEqual(self.cli("verify", str(self.root), "--legacy")[0], 0)
        self.assertEqual(self.cli("verify", str(self.root), "--claims", "--legacy")[0], 0)
        code, out, _err = self.cli("index", "--root", str(self.root), "--legacy")
        self.assertEqual(code, 0, out)
        self.assertTrue((self.root / "index.json").is_file())

    def test_legacy_flag_on_gate_and_query(self):
        self.legacy()
        code, _out, err = self.cli("gate", "--root", str(self.root), "--run-id", "nope", "--legacy")
        self.assertNotIn(MESSAGE, err)  # past the guard: the ledger error is the legacy behaviour
        self.cli("index", "--root", str(self.root), "--legacy")
        code, out, err = self.cli("query", "--root", str(self.root), "--legacy")
        self.assertEqual(code, 0, out + err)

    def test_an_ontology_root_needs_no_flag(self):
        shutil.copytree(FIXTURE, self.root)
        self.assertEqual(self.cli("verify", str(self.root))[0], 0)
        self.assertEqual(self.cli("index", "--root", str(self.root))[0], 0)
        self.assertEqual(self.cli("query", "--root", str(self.root))[0], 0)

    def test_self_reported_gate_and_ingest_need_no_ontology(self):
        code, out, _err = self.cli("gate", "--self-report")
        self.assertIn("Decision", out)
        code, _out, err = self.cli("ingest", "notes.unsupported")
        self.assertEqual(code, 1)
        self.assertNotIn("ontology.yaml", err)

    def test_a_missing_directory_keeps_its_own_message(self):
        code, out, err = self.cli("verify", str(self.root / "absent"))
        self.assertEqual(code, 1)
        self.assertIn("not a directory", out)
        self.assertNotIn(MESSAGE, err)
        code, _out, err = self.cli("index", "--root", str(self.root / "absent"))
        self.assertEqual(code, 1)
        self.assertIn("Directory not found", err)

    def test_legacy_verify_output_is_unchanged(self):
        self.legacy()
        code, out, err = self.cli("verify", str(self.root), "--legacy")
        self.assertEqual((code, out, err), (0, "files: 3\nanchors: 3\nfailures: 0\n", WARNING))


if __name__ == "__main__":
    unittest.main()
