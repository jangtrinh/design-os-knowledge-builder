"""A freeze and a command capture each spend one call, and stop before the work when none remain."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_ontology_support import run_cli

SENTENCE = "The measured sample shows alpha holds across every recorded case. "
HTML = "<html><body><p>" + (SENTENCE * 4) + "</p></body></html>"
URL = "https://example.com/alpha"
EXHAUSTED = "budget exhausted (used 0 of 0): the gate will PAUSE_BUDGET"


def _init(root, budget):
    code, out, err = run_cli(
        ["knowledge-builder", "run", "init", "--root", str(root), "--id", "r1", "--budget", str(budget)]
    )
    assert code == 0, out + err


def _state(root):
    return json.loads((Path(root) / "_evidence" / "r1" / "state.json").read_text(encoding="utf-8"))


class CallBudgetTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "root"
        self.root.mkdir()

    def test_successful_freeze_spends_one_call(self):
        _init(self.root, 3)
        page = Path(self._tmp.name) / "page.html"
        page.write_text(HTML, encoding="utf-8")
        code, out, err = run_cli(
            [
                "knowledge-builder", "ingest", "--freeze", "--from-file", str(page),
                "--root", str(self.root), "--run", "r1", "--stem", "alpha", URL,
            ]
        )
        self.assertEqual(code, 0, out + err)
        state = _state(self.root)
        self.assertEqual(state["remaining_budget_calls"], 2)
        self.assertEqual(state["budget_used"], 1)

    def test_fetched_freeze_also_spends_one_call(self):
        _init(self.root, 3)
        with patch("knowledge_builder.processors.web_freeze.fetch_html", return_value=HTML):
            code, out, err = run_cli(
                ["knowledge-builder", "ingest", "--freeze", "--root", str(self.root), "--run", "r1", "--stem", "alpha", URL]
            )
        self.assertEqual(code, 0, out + err)
        state = _state(self.root)
        self.assertEqual(state["remaining_budget_calls"], 2)
        self.assertEqual(state["budget_used"], 1)

    def test_exhausted_freeze_does_not_fetch(self):
        _init(self.root, 0)
        calls = []

        def fetch(url):
            calls.append(url)
            return HTML

        with patch("knowledge_builder.processors.web_freeze.fetch_html", fetch):
            code, out, err = run_cli(
                ["knowledge-builder", "ingest", "--freeze", "--root", str(self.root), "--run", "r1", "--stem", "alpha", URL]
            )
        self.assertNotEqual(code, 0)
        self.assertEqual(calls, [])
        self.assertIn(EXHAUSTED, err)
        self.assertFalse((self.root / "_evidence" / "r1" / "sources" / "alpha.txt").exists())

    def test_exhausted_from_file_refuses_before_reading(self):
        _init(self.root, 0)
        missing = Path(self._tmp.name) / "missing.html"
        code, out, err = run_cli(
            [
                "knowledge-builder", "ingest", "--freeze", "--from-file", str(missing),
                "--root", str(self.root), "--run", "r1", "--stem", "alpha", URL,
            ]
        )
        self.assertNotEqual(code, 0)
        self.assertIn(EXHAUSTED, err)
        self.assertNotIn("could not read", err)

    def test_exhausted_exec_does_not_run(self):
        _init(self.root, 0)
        marker = Path(self._tmp.name) / "ran"
        code, out, err = run_cli(
            [
                "knowledge-builder", "run", "exec", "--root", str(self.root), "--id", "r1",
                "--stem", "ran", "--", sys.executable, "-c", f"open({str(marker)!r}, 'w').write('x')",
            ]
        )
        self.assertNotEqual(code, 0)
        self.assertIn(EXHAUSTED, err)
        self.assertFalse(marker.exists())
        self.assertFalse((self.root / "_evidence" / "r1" / "sources" / "ran.txt").exists())

    def test_bad_stem_does_not_spend_a_call(self):
        _init(self.root, 3)
        before = (self.root / "_evidence" / "r1" / "state.json").read_bytes()
        code, out, err = run_cli(
            ["knowledge-builder", "ingest", "--freeze", "--root", str(self.root), "--run", "r1", "--stem", "Bad", URL]
        )
        self.assertNotEqual(code, 0)
        self.assertIn("kebab-case", err)
        self.assertNotIn("budget exhausted", err)
        self.assertEqual((self.root / "_evidence" / "r1" / "state.json").read_bytes(), before)

    def test_exec_spends_one_call_even_when_the_command_fails(self):
        _init(self.root, 3)
        code, out, err = run_cli(
            [
                "knowledge-builder", "run", "exec", "--root", str(self.root), "--id", "r1",
                "--stem", "fail", "--", sys.executable, "-c", "import sys; sys.exit(3)",
            ]
        )
        self.assertEqual(code, 0, out + err)
        state = _state(self.root)
        self.assertEqual(state["remaining_budget_calls"], 2)
        self.assertEqual(state["budget_used"], 1)
