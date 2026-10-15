"""Helpers for the es-knowledge-forge skill tests: paths, script runner, one built pack per example."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "skills" / "es-knowledge-forge"
GENERATOR = REPO / "scripts" / "generate-skill-contract.py"
EXAMPLES = sorted((SKILL / "examples").glob("*.json"))


def run_script(script, *args, skill=SKILL):
    """Run a skill script with the repo as product root; (returncode, stdout lines, stderr)."""
    done = subprocess.run([sys.executable, "-B", str(skill / script), *map(str, args), "--repo-root", str(REPO)],
                          capture_output=True, text=True, timeout=300)
    return done.returncode, done.stdout.splitlines(), done.stderr


def validate(root, skill=SKILL):
    return run_script("validate.py", "--root", root, skill=skill)


def browser_available():
    sys.path.insert(0, str(SKILL))
    try:
        from look import find_browser
        from forge_common import CannotRun
    finally:
        sys.path.remove(str(SKILL))
    try:
        find_browser(None)
    except CannotRun:
        return False
    return True


class BuiltExamples(unittest.TestCase):
    """Builds each example once per class into class_tmp; mutate() hands out a private copy."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.packs = {}
        for spec in EXAMPLES:
            out = Path(cls._tmp.name) / spec.stem
            code, lines, err = run_script("build.py", "--spec", spec, "--output-dir", out)
            assert code == 0, f"{spec.name}: {err} {lines}"
            cls.packs[spec.stem] = out

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def mutate(self, name):
        """Private writable copy of a built example."""
        target = Path(tempfile.mkdtemp(dir=self._tmp.name)) / name
        shutil.copytree(self.packs[name], target)
        return target

    def only_line(self, root, check):
        code, lines, err = validate(root)
        self.assertEqual(code, 1, (lines, err))
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(f"{check}: "), lines)
        return lines[0]


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
