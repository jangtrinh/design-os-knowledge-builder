"""P1.1 run driver: init, record, status. Relative URIs only. No model calls.

record of an atom whose source_uri is file:///Users/... exits non-zero and
leaves evidence.jsonl unchanged. A relative uri appends one line that
load_atoms can round-trip.
"""

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def _run(argv, stdin=""):
    import knowledge_builder.cli as cli_mod

    stdout = io.StringIO()
    stderr = io.StringIO()
    with (
        patch("sys.argv", argv),
        patch("sys.stdout", stdout),
        patch("sys.stderr", stderr),
        patch("sys.stdin", io.StringIO(stdin)),
    ):
        try:
            cli_mod.main()
            code = 0
        except SystemExit as caught:
            code = caught.code
    return code, stdout.getvalue(), stderr.getvalue()


def _atom(source_uri, run_id="run-1"):
    return {
        "id": "atom-1",
        "run_id": run_id,
        "claim_type": "FACT",
        "statement": "The frozen copy lives under sources/.",
        "source_uri": source_uri,
        "source_digest": "a" * 64,
        "captured_at": "2026-10-12T00:00:00Z",
        "confidence": "HIGH",
        "verified_by_code": False,
        "metadata": {"claim": "R1"},
    }


class TestRunDriver(unittest.TestCase):
    def test_record_rejects_absolute_file_uri_and_round_trips_relative(self):
        """file:///Users/... is refused. A relative uri appends one load_atoms line."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code, out, err = _run(
                [
                    "knowledge-builder",
                    "run",
                    "init",
                    "--root",
                    str(root),
                    "--id",
                    "run-1",
                    "--budget",
                    "4",
                ]
            )
            self.assertEqual(code, 0, out + err)
            evidence = root / "_evidence" / "run-1" / "evidence.jsonl"
            before = evidence.read_bytes()

            bad = _atom("file:///Users/jangtrinh/secret.txt")
            code, out, err = _run(
                [
                    "knowledge-builder",
                    "run",
                    "record",
                    "--root",
                    str(root),
                    "--id",
                    "run-1",
                ],
                stdin=json.dumps(bad),
            )
            self.assertNotEqual(code, 0, out + err)
            self.assertEqual(evidence.read_bytes(), before)

            relative = "_evidence/run-1/sources/note.md"
            good = _atom(relative)
            with patch("knowledge_builder.research.ledger.os.fsync") as fsync:
                code, out, err = _run(
                    [
                        "knowledge-builder",
                        "run",
                        "record",
                        "--root",
                        str(root),
                        "--id",
                        "run-1",
                    ],
                    stdin=json.dumps(good),
                )
            self.assertEqual(code, 0, out + err)
            self.assertTrue(fsync.called, "record must fsync the appended atom")

            from knowledge_builder.research.ledger import AtomicResearchLedger

            atoms = AtomicResearchLedger("run-1", base_dir=root / "_evidence").load_atoms()
            self.assertEqual(len(atoms), 1)
            got = atoms[0]
            self.assertEqual(got.id, good["id"])
            self.assertEqual(got.run_id, good["run_id"])
            self.assertEqual(got.claim_type, good["claim_type"])
            self.assertEqual(got.statement, good["statement"])
            self.assertEqual(got.source_uri, relative)
            self.assertEqual(got.source_digest, good["source_digest"])
            self.assertEqual(got.captured_at, good["captured_at"])
            self.assertEqual(got.confidence, good["confidence"])
            self.assertEqual(got.verified_by_code, good["verified_by_code"])
            self.assertEqual(got.metadata, good["metadata"])
            lines = evidence.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)

    def test_init_creates_run_tree_and_status_prints_cursor(self):
        """init creates state.json, evidence.jsonl, and sources/. status prints that cursor."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code, out, err = _run(
                [
                    "knowledge-builder",
                    "run",
                    "init",
                    "--root",
                    str(root),
                    "--id",
                    "run-1",
                    "--budget",
                    "4",
                ]
            )
            self.assertEqual(code, 0, out + err)
            run = root / "_evidence" / "run-1"
            self.assertTrue((run / "state.json").is_file())
            self.assertTrue((run / "evidence.jsonl").is_file())
            self.assertEqual((run / "evidence.jsonl").read_bytes(), b"")
            self.assertTrue((run / "sources").is_dir())
            state = json.loads((run / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["run_id"], "run-1")
            self.assertEqual(state["status"], "RUNNING")
            self.assertEqual(state["remaining_budget_calls"], 4)
            self.assertEqual(state["budget_total"], 4)

            code, out, err = _run(
                [
                    "knowledge-builder",
                    "run",
                    "status",
                    "--root",
                    str(root),
                    "--id",
                    "run-1",
                ]
            )
            self.assertEqual(code, 0, out + err)
            cursor = json.loads(out)
            self.assertEqual(cursor["run_id"], "run-1")
            self.assertEqual(cursor["status"], "RUNNING")
            self.assertEqual(cursor["remaining_budget_calls"], 4)
            self.assertEqual(cursor["round"], 0)


if __name__ == "__main__":
    unittest.main()
