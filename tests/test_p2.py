"""P2: ledger lock, entailment notes as data, optional extractors that refuse.

Two processes appending 50 atoms each must leave 100 valid lines, and the
append must create a sibling evidence.jsonl.lock. A malformed
review.json entailment_notes value does not change the gate, and run status
reports it. Audio and table-OCR processors raise RuntimeError naming the
missing extra and binary. They import nothing from those extras.
"""

import hashlib
import io
import json
import multiprocessing
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
            code = caught.code if isinstance(caught.code, int) else 1
    return code, stdout.getvalue(), stderr.getvalue()


def _append_atoms(base_dir, run_id, start, count):
    """Child-process target. Appends `count` atoms starting at `start`."""
    from knowledge_builder.research.ledger import AtomicResearchLedger, EvidenceAtom

    ledger = AtomicResearchLedger(run_id, base_dir=Path(base_dir))
    for offset in range(count):
        number = start + offset
        ledger.record_atom(
            EvidenceAtom(
                id=f"atom-{number}",
                run_id=run_id,
                claim_type="FACT",
                statement=f"statement {number}",
                source_uri=f"sources/n-{number}.txt",
                source_digest="a" * 64,
                captured_at="2026-10-12T00:00:00Z",
                confidence="HIGH",
                verified_by_code=False,
                metadata={"n": number},
            )
        )


def _sha(body):
    return hashlib.sha256(body).hexdigest()


def _atom(atom_id, claim_id, source_uri, digest, *, claim_type="FACT", metadata=None, quote=None):
    meta = {"claim": claim_id}
    if metadata:
        meta.update(metadata)
    atom = {
        "id": atom_id,
        "run_id": "run-1",
        "claim_type": claim_type,
        "statement": f"support for {claim_id}",
        "source_uri": source_uri,
        "source_digest": digest,
        "captured_at": "2026-10-12T00:00:00Z",
        "confidence": "HIGH",
        "verified_by_code": False,
        "metadata": meta,
    }
    if quote is not None:
        atom["quote"] = quote
    return atom


class TestP2LedgerLockNotesExtractors(unittest.TestCase):
    def test_two_processes_append_50_each_yield_100_valid_lines(self):
        """Two writers, 50 atoms each, leave 100 parseable lines and a sibling .lock."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "_evidence"
            base.mkdir()
            ctx = multiprocessing.get_context("spawn")
            first = ctx.Process(target=_append_atoms, args=(str(base), "run-lock", 0, 50))
            second = ctx.Process(target=_append_atoms, args=(str(base), "run-lock", 50, 50))
            first.start()
            second.start()
            first.join(60)
            second.join(60)
            self.assertFalse(first.is_alive())
            self.assertFalse(second.is_alive())
            self.assertEqual(first.exitcode, 0)
            self.assertEqual(second.exitcode, 0)

            evidence = base / "run-lock" / "evidence.jsonl"
            lock = evidence.with_name(evidence.name + ".lock")
            lines = [line for line in evidence.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(lines), 100)
            ids = []
            for line in lines:
                item = json.loads(line)
                self.assertEqual(item["run_id"], "run-lock")
                self.assertTrue(item["source_uri"].startswith("sources/"))
                ids.append(item["id"])
            self.assertEqual(set(ids), {f"atom-{i}" for i in range(100)})
            self.assertEqual(len(ids), 100)
            self.assertTrue(lock.is_file(), "append must flock a sibling evidence.jsonl.lock")
            self.assertEqual(lock.parent, evidence.parent)
            self.assertTrue(lock.name.endswith(".lock"))

    def test_malformed_entailment_notes_ignored_by_gate_reported_by_status(self):
        """A bad entailment_notes value still exits 0. run status names the problem.

        A well-formed list is echoed as data and still does not change the gate.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = root / "_evidence" / "run-1"
            sources = run / "sources"
            sources.mkdir(parents=True)
            body_a = b"claim alpha holds\n"
            body_b = b"known failure mode\n"
            rel_a = "_evidence/run-1/sources/a.txt"
            rel_b = "_evidence/run-1/sources/b.txt"
            (root / rel_a).write_bytes(body_a)
            (root / rel_b).write_bytes(body_b)
            claim = _atom(
                "atom-c1",
                "c1",
                rel_a,
                _sha(body_a),
                metadata={"command": "python3 -m unittest"},
                quote="claim alpha holds",
            )
            failure = _atom(
                "atom-fail",
                "fail-1",
                rel_b,
                _sha(body_b),
                claim_type="FAILURE_MODE",
                quote="known failure mode",
            )
            (run / "evidence.jsonl").write_text(
                json.dumps(claim) + "\n" + json.dumps(failure) + "\n",
                encoding="utf-8",
            )
            state = {
                "run_id": "run-1",
                "round": 3,
                "status": "RUNNING",
                "budget_used": 1,
                "budget_total": 4,
                "remaining_budget_calls": 2,
                "gaps": [],
                "resolved": [],
                "required_claim_ids": ["c1"],
                "minimum_independent_sources": 2,
                "consecutive_low_delta_rounds": 3,
                "last_weighted_delta": 0.01,
                "has_viable_probe_remaining": False,
                "is_target_version_matched": True,
                "researcher_runtime": "grok",
            }
            state_path = run / "state.json"
            state_path.write_text(json.dumps(state), encoding="utf-8")
            review_path = run / "review.json"
            review_path.write_text(
                json.dumps(
                    {
                        "passed": True,
                        "reviewer_runtime": "codex",
                        "entailment_notes": "not-a-list",
                    }
                ),
                encoding="utf-8",
            )
            gate_argv = [
                "knowledge-builder",
                "gate",
                "--root",
                str(root),
                "--run-id",
                "run-1",
            ]
            code, out, err = _run(gate_argv)
            self.assertEqual(code, 0, out + err)
            self.assertIn("STOP_SUFFICIENT", out)
            disk_before = state_path.read_text(encoding="utf-8")

            code, out, err = _run(
                ["knowledge-builder", "run", "status", "--root", str(root), "--id", "run-1"]
            )
            self.assertEqual(code, 0, out + err)
            report = json.loads(out)
            self.assertEqual(
                report.get("entailment_notes_error"),
                "ignored: entailment_notes must be a list of {claim_id, note} strings",
            )
            self.assertNotIn("entailment_notes", report)
            self.assertEqual(state_path.read_text(encoding="utf-8"), disk_before)

            notes = [{"claim_id": "c1", "note": "the quote entails the claim"}]
            review_path.write_text(
                json.dumps(
                    {
                        "passed": True,
                        "reviewer_runtime": "codex",
                        "entailment_notes": notes,
                    }
                ),
                encoding="utf-8",
            )
            code, out, err = _run(gate_argv)
            self.assertEqual(code, 0, out + err)
            self.assertIn("STOP_SUFFICIENT", out)
            code, out, err = _run(
                ["knowledge-builder", "run", "status", "--root", str(root), "--id", "run-1"]
            )
            self.assertEqual(code, 0, out + err)
            report = json.loads(out)
            self.assertEqual(report.get("entailment_notes"), notes)
            self.assertNotIn("entailment_notes_error", report)
            self.assertEqual(state_path.read_text(encoding="utf-8"), disk_before)

    def test_audio_and_table_ocr_raise_naming_missing_extra(self):
        """audio/ocr are optional extras. Calling the processors raises, and imports neither."""
        import sys

        text = Path("pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("dependencies = []", text)
        section = text.split("[project.optional-dependencies]", 1)[1].split("\n[", 1)[0]
        self.assertRegex(section, r"(?m)^audio\s*=")
        self.assertRegex(section, r"(?m)^ocr\s*=")

        before = set(sys.modules)
        from knowledge_builder.processors.audio import process_audio
        from knowledge_builder.processors.table_ocr import process_table_ocr

        added = set(sys.modules) - before
        banned = ("whisper", "tesseract", "pytesseract", "paddleocr", "easyocr")
        self.assertFalse(any(any(token in name for token in banned) for name in added))

        with self.assertRaises(RuntimeError) as caught:
            process_audio("clip.wav")
        message = str(caught.exception)
        self.assertIn("audio", message)
        self.assertIn("whisper", message)

        with self.assertRaises(RuntimeError) as caught:
            process_table_ocr("table.png")
        message = str(caught.exception)
        self.assertIn("ocr", message)
        self.assertIn("tesseract", message)


if __name__ == "__main__":
    unittest.main()
