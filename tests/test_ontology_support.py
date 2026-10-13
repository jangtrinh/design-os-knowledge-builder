"""Shared helpers for the ontology tests: a writable copy of the fixture root and a CLI runner."""

import io
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "ontology" / "root"


def run_cli(argv):
    import knowledge_builder.cli as cli_mod

    out, err = io.StringIO(), io.StringIO()
    with patch("sys.argv", argv), patch("sys.stdout", out), patch("sys.stderr", err):
        try:
            cli_mod.main()
            code = 0
        except SystemExit as caught:
            code = caught.code
    return code, out.getvalue(), err.getvalue()


class RootCase(unittest.TestCase):
    """Each test gets a fresh copy of the fixture root in self.root."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "root"
        shutil.copytree(FIXTURE, self.root)

    def read(self, rel):
        return (self.root / rel).read_text(encoding="utf-8")

    def write(self, rel, text):
        (self.root / rel).write_text(text, encoding="utf-8")

    def replace(self, rel, old, new):
        text = self.read(rel)
        self.assertIn(old, text)
        self.write(rel, text.replace(old, new, 1))
