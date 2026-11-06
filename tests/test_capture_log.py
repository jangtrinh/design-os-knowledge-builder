"""Captures are logged by the command that wrote the file."""

import hashlib
import json
import shlex
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import knowledge_builder
from tests.test_ontology_support import run_cli

SENTENCE = "The measured sample shows alpha holds across every recorded case. "
HTML = "<html><body><p>" + (SENTENCE * 4) + "</p></body></html>"
URL = "https://example.com/alpha"


def _init(root, budget="4"):
    code, out, err = run_cli(
        ["knowledge-builder", "run", "init", "--root", str(root), "--id", "r1", "--budget", budget]
    )
    assert code == 0, out + err


def _lines(root):
    path = Path(root) / "_evidence" / "r1" / "captures.jsonl"
    assert path.is_file(), path
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class CaptureLogTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "root"
        self.root.mkdir()
        _init(self.root)

    def test_freeze_appends_fetched_capture(self):
        with patch("knowledge_builder.processors.web_freeze.fetch_html", return_value=HTML) as fetch:
            code, out, err = run_cli(
                ["knowledge-builder", "ingest", "--freeze", "--root", str(self.root), "--run", "r1", "--stem", "alpha", URL]
            )
        self.assertEqual(code, 0, out + err)
        fetch.assert_called_once()
        rows = _lines(self.root)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        rel = "_evidence/r1/sources/alpha.txt"
        digest = hashlib.sha256((self.root / rel).read_bytes()).hexdigest()
        self.assertEqual(row["path"], rel)
        self.assertEqual(row["sha256"], digest)
        self.assertEqual(row["origin"], "fetched")
        self.assertEqual(row["url"], URL)
        self.assertIsNone(row["command"])
        self.assertIsNone(row["exit_code"])
        self.assertTrue(row["captured_at"].endswith("+00:00"))
        self.assertEqual(row["tool_version"], knowledge_builder.__version__)

    def test_from_file_appends_without_fetching(self):
        page = Path(self._tmp.name) / "page.html"
        page.write_text(HTML, encoding="utf-8")

        def boom(url):
            raise AssertionError(f"fetch called for {url}")

        with patch("knowledge_builder.processors.web_freeze.fetch_html", boom):
            code, out, err = run_cli(
                [
                    "knowledge-builder", "ingest", "--freeze", "--from-file", str(page),
                    "--root", str(self.root), "--run", "r1", "--stem", "local", URL,
                ]
            )
        self.assertEqual(code, 0, out + err)
        row = _lines(self.root)[0]
        self.assertEqual(row["origin"], "from-file")
        self.assertEqual(row["url"], URL)
        self.assertIsNone(row["command"])

    def test_second_freeze_appends(self):
        page = Path(self._tmp.name) / "page.html"
        page.write_text(HTML, encoding="utf-8")
        for stem in ("one", "two"):
            code, out, err = run_cli(
                [
                    "knowledge-builder", "ingest", "--freeze", "--from-file", str(page),
                    "--root", str(self.root), "--run", "r1", "--stem", stem, URL,
                ]
            )
            self.assertEqual(code, 0, out + err)
        self.assertEqual([row["path"] for row in _lines(self.root)], [
            "_evidence/r1/sources/one.txt",
            "_evidence/r1/sources/two.txt",
        ])

    def test_exec_writes_header_and_logs_executed(self):
        code, out, err = run_cli(
            [
                "knowledge-builder", "run", "exec", "--root", str(self.root), "--id", "r1",
                "--stem", "ran", "--", sys.executable, "-c", "print('hello from the captured command output')",
            ]
        )
        self.assertEqual(code, 0, out + err)
        rel = "_evidence/r1/sources/ran.txt"
        text = (self.root / rel).read_text(encoding="utf-8")
        command = shlex.join([sys.executable, "-c", "print('hello from the captured command output')"])
        self.assertTrue(text.startswith(f"Command: {command}\n"), text)
        self.assertIn("Exit: 0\n", text)
        self.assertIn("Ran: ", text)
        self.assertIn("hello from the captured command output", text.split("\n\n", 1)[-1])
        self.assertIn(f"Path: {rel}", out)
        self.assertIn("SHA256: ", out)
        self.assertIn("Exit: 0", out)
        row = _lines(self.root)[0]
        self.assertEqual(row["origin"], "executed")
        self.assertEqual(row["exit_code"], 0)
        self.assertEqual(row["command"], [sys.executable, "-c", "print('hello from the captured command output')"])
        self.assertIsNone(row["url"])
        self.assertEqual(row["sha256"], hashlib.sha256((self.root / rel).read_bytes()).hexdigest())

    def test_failing_command_is_still_captured(self):
        code, out, err = run_cli(
            [
                "knowledge-builder", "run", "exec", "--root", str(self.root), "--id", "r1",
                "--stem", "fail", "--", sys.executable, "-c", "import sys; sys.exit(3)",
            ]
        )
        self.assertEqual(code, 0, out + err)
        text = (self.root / "_evidence" / "r1" / "sources" / "fail.txt").read_text(encoding="utf-8")
        self.assertIn("Exit: 3\n", text)
        self.assertEqual(_lines(self.root)[0]["exit_code"], 3)
        self.assertIn("Exit: 3", out)

    def test_exec_refuses_to_overwrite(self):
        argv = [
            "knowledge-builder", "run", "exec", "--root", str(self.root), "--id", "r1",
            "--stem", "ran", "--", sys.executable, "-c", "print('first capture stays')",
        ]
        code, out, err = run_cli(argv)
        self.assertEqual(code, 0, out + err)
        before = (self.root / "_evidence" / "r1" / "sources" / "ran.txt").read_bytes()
        code, out, err = run_cli(argv)
        self.assertNotEqual(code, 0, out)
        self.assertEqual((self.root / "_evidence" / "r1" / "sources" / "ran.txt").read_bytes(), before)
        self.assertEqual(len(_lines(self.root)), 1)

    def test_exec_timeout_writes_nothing(self):
        code, out, err = run_cli(
            [
                "knowledge-builder", "run", "exec", "--root", str(self.root), "--id", "r1",
                "--stem", "slow", "--timeout", "1", "--", sys.executable, "-c", "import time; time.sleep(5)",
            ]
        )
        self.assertNotEqual(code, 0)
        self.assertIn("timed out", err.lower())
        self.assertFalse((self.root / "_evidence" / "r1" / "sources" / "slow.txt").exists())
        self.assertFalse((self.root / "_evidence" / "r1" / "captures.jsonl").exists())

    def test_empty_argv_does_not_run(self):
        code, out, err = run_cli(
            ["knowledge-builder", "run", "exec", "--root", str(self.root), "--id", "r1", "--stem", "empty", "--"]
        )
        self.assertNotEqual(code, 0)
        self.assertNotIn("invalid choice", err)
        self.assertFalse((self.root / "_evidence" / "r1" / "sources" / "empty.txt").exists())

    def test_exec_truncates_combined_output(self):
        import knowledge_builder.research.run_exec as run_exec

        with patch.object(run_exec, "MAX_CAPTURE_BYTES", 32):
            code, out, err = run_cli(
                [
                    "knowledge-builder", "run", "exec", "--root", str(self.root), "--id", "r1",
                    "--stem", "big", "--", sys.executable, "-c", "print('x' * 200)",
                ]
            )
        self.assertEqual(code, 0, out + err)
        text = (self.root / "_evidence" / "r1" / "sources" / "big.txt").read_text(encoding="utf-8")
        body = text.split("\n\n", 1)[1]
        self.assertLessEqual(len(body.encode("utf-8")), 32)
