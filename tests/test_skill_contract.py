"""A3/M4: the generated CLI contract is current and validate refuses an edited copy."""

import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.skill_support import GENERATOR, REPO, SKILL, validate

try:
    from tests.skill_support import BuiltExamples
except ImportError:  # pragma: no cover
    BuiltExamples = unittest.TestCase


def load_generator():
    spec = importlib.util.spec_from_file_location("generate_skill_contract", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestContractGenerator(unittest.TestCase):
    def test_a3_check_exits_zero_on_the_committed_contract(self):
        done = subprocess.run([sys.executable, "-B", str(GENERATOR), "--check"], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("ok: contract", done.stdout)

    def test_header_hash_matches_the_body_and_the_surface_is_complete(self):
        import hashlib

        first, _, body = (SKILL / "contract.txt").read_bytes().partition(b"\n")
        self.assertEqual(first.decode(), "# sha256: " + hashlib.sha256(body).hexdigest())
        text = body.decode()
        for command in ("ingest", "gate", "lint", "verify", "index", "run init", "run record", "run measure", "run state set",
                        "query", "action", "pack init", "pack status", "pack check"):
            self.assertIn(f"## knowledge-builder {command}", text)
        for needle in ("--freeze", "--material", "--write-state", "--batch", "--param", "promote-claim", "arxiv.org"):
            self.assertIn(needle, text)

    def test_check_fails_on_a_stale_contract(self):
        module = load_generator()
        with tempfile.TemporaryDirectory() as tmp:
            stale = Path(tmp) / "contract.txt"
            stale.write_bytes((SKILL / "contract.txt").read_bytes().replace(b"--claims", b"--clamis", 1))
            module.TARGET = stale
            old = sys.argv
            sys.argv = ["generate-skill-contract.py", "--check"]
            try:
                self.assertEqual(module.main(), 1)
            finally:
                sys.argv = old

    def test_generation_is_deterministic(self):
        module = load_generator()
        self.assertEqual(module.render(), module.render())
        self.assertEqual(module.render(), (SKILL / "contract.txt").read_bytes())


class TestValidateRefusesEditedContract(BuiltExamples):
    def test_edited_contract_copy_is_one_contract_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "es-knowledge-forge"
            shutil.copytree(SKILL, copy, ignore=shutil.ignore_patterns("__pycache__"))
            (copy / "contract.txt").write_bytes((copy / "contract.txt").read_bytes() + b"  --invented  a flag the CLI lacks\n")
            code, lines, err = validate(self.packs["tiny-document-pack"], skill=copy)
        self.assertEqual(code, 1, (lines, err))
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("contract: "), lines)
