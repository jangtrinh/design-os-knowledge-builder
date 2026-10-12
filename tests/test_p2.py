"""P2: ledger lock, entailment notes as data, optional extractors.

Two processes appending 50 atoms each must leave 100 valid lines, and an
append blocks while another process holds the sibling evidence.jsonl.lock.
A malformed review.json entailment_notes value does not change the gate, and
run status reports it. Audio and table-OCR processors return text printed by
whisper, whisper-cli, or tesseract when that binary is on PATH. They raise
RuntimeError when the binary is missing or exits non-zero, and they import
nothing from those extras.
"""

import fcntl
import hashlib
import io
import json
import multiprocessing
import os
import tempfile
import time
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
        ledger.record_atom(_fact_atom(run_id, number))


def _fact_atom(run_id, number):
    from knowledge_builder.research.ledger import EvidenceAtom

    return EvidenceAtom(
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


def _hold_exclusive_lock(lock_path, acquired_path, release_path):
    """Hold LOCK_EX on the sibling ledger lock until the release file appears."""
    fd = os.open(lock_path, os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        Path(acquired_path).write_text("held", encoding="utf-8")
        deadline = time.time() + 30
        while not Path(release_path).exists():
            if time.time() > deadline:
                break
            time.sleep(0.05)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _append_one_atom(base_dir, run_id, ready_path):
    """Signal, then append one atom. Blocks while the sibling lock is held."""
    from knowledge_builder.research.ledger import AtomicResearchLedger

    ledger = AtomicResearchLedger(run_id, base_dir=Path(base_dir))
    atom = _fact_atom(run_id, "blocked")
    Path(ready_path).write_text("ready", encoding="utf-8")
    ledger.record_atom(atom)


def _wait_for_file(path, seconds):
    deadline = time.time() + seconds
    while not Path(path).exists():
        if time.time() > deadline:
            return False
        time.sleep(0.02)
    return True


def _stub_script(text, code=0):
    """Executable stub. Absolute interpreter so an emptied PATH cannot hide it."""
    import sys

    lines = [
        f"#!{sys.executable}",
        "import sys",
        f"sys.stdout.write({text!r})",
        "sys.stdout.flush()",
    ]
    if code:
        lines.append(f"raise SystemExit({code})")
    return "\n".join(lines) + "\n"


def _install_stub(directory, name, script):
    path = Path(directory) / name
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)
    return path


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

    def test_append_blocks_while_sibling_lock_held(self):
        """An append from another process blocks on the sibling .lock.

        After ~0.3s the ledger is unchanged. After the holder releases the
        exclusive flock, the append completes.
        """
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            run_id = "run-contend"
            stage = base / run_id
            stage.mkdir()
            evidence = stage / "evidence.jsonl"
            seed = '{"id":"seed"}\n'
            evidence.write_text(seed, encoding="utf-8")
            lock_path = evidence.with_name(evidence.name + ".lock")
            lock_path.write_bytes(b"")

            acquired_path = stage / "acquired"
            release_path = stage / "release"
            ready_path = stage / "ready"
            ctx = multiprocessing.get_context("spawn")
            holder = ctx.Process(
                target=_hold_exclusive_lock,
                args=(str(lock_path), str(acquired_path), str(release_path)),
            )
            appender = ctx.Process(
                target=_append_one_atom,
                args=(str(base), run_id, str(ready_path)),
            )
            holder.start()
            try:
                self.assertTrue(
                    _wait_for_file(acquired_path, 5),
                    "holder did not acquire the lock",
                )
                appender.start()
                self.assertTrue(
                    _wait_for_file(ready_path, 5),
                    "appender did not reach record_atom",
                )
                time.sleep(0.3)
                self.assertTrue(
                    appender.is_alive(),
                    "append must block while the sibling lock is held",
                )
                self.assertEqual(evidence.read_text(encoding="utf-8"), seed)
                release_path.write_text("go", encoding="utf-8")
                appender.join(10)
                self.assertFalse(appender.is_alive())
                self.assertEqual(appender.exitcode, 0)
                lines = [
                    line
                    for line in evidence.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                self.assertEqual(len(lines), 2)
                self.assertEqual(json.loads(lines[0])["id"], "seed")
                self.assertEqual(json.loads(lines[1])["id"], "atom-blocked")
            finally:
                release_path.write_text("go", encoding="utf-8")
                if holder.pid is not None:
                    holder.join(10)
                if appender.pid is not None:
                    appender.join(10)
                    if appender.is_alive():
                        appender.terminate()
                        appender.join(5)

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

        with patch.dict(os.environ, {"PATH": ""}):
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

    def test_whisper_stub_on_path_returns_printed_transcript(self):
        """A whisper executable that prints known text is the transcript."""
        from knowledge_builder.processors.audio import process_audio

        with tempfile.TemporaryDirectory() as tmp:
            _install_stub(tmp, "whisper", _stub_script("known transcript\n"))
            with patch.dict(os.environ, {"PATH": tmp}):
                text = process_audio("clip.wav")
        self.assertEqual(text, "known transcript\n")

    def test_whisper_cli_stub_on_path_returns_printed_transcript(self):
        """whisper-cli is used when whisper itself is not on PATH."""
        from knowledge_builder.processors.audio import process_audio

        with tempfile.TemporaryDirectory() as tmp:
            _install_stub(tmp, "whisper-cli", _stub_script("cpp transcript\n"))
            with patch.dict(os.environ, {"PATH": tmp}):
                text = process_audio("clip.wav")
        self.assertEqual(text, "cpp transcript\n")

    def test_tesseract_stub_on_path_returns_printed_text(self):
        """tesseract stdout is the table text for plain and tsv layouts."""
        from knowledge_builder.processors.table_ocr import process_table_ocr

        with tempfile.TemporaryDirectory() as tmp:
            _install_stub(tmp, "tesseract", _stub_script("known table\n"))
            with patch.dict(os.environ, {"PATH": tmp}):
                plain = process_table_ocr("table.png")
                tsv = process_table_ocr("table.png", layout="tsv")
        self.assertEqual(plain, "known table\n")
        self.assertEqual(tsv, "known table\n")

    def test_extractor_nonzero_exit_raises(self):
        """A non-zero whisper or tesseract exit raises and does not return its text."""
        from knowledge_builder.processors.audio import process_audio
        from knowledge_builder.processors.table_ocr import process_table_ocr

        fail = _stub_script("placeholder transcript\n", code=1)
        with tempfile.TemporaryDirectory() as tmp:
            _install_stub(tmp, "whisper", fail)
            _install_stub(tmp, "tesseract", fail)
            with patch.dict(os.environ, {"PATH": tmp}):
                with self.assertRaises(RuntimeError) as audio_caught:
                    process_audio("clip.wav")
                with self.assertRaises(RuntimeError) as ocr_caught:
                    process_table_ocr("table.png")
        audio_message = str(audio_caught.exception)
        ocr_message = str(ocr_caught.exception)
        self.assertIn("exited", audio_message)
        self.assertIn("1", audio_message)
        self.assertNotIn("placeholder transcript", audio_message)
        self.assertIn("exited", ocr_message)
        self.assertIn("1", ocr_message)
        self.assertNotIn("placeholder transcript", ocr_message)

    def test_whisper_mkdtemp_permission_error_raises_runtime_error(self):
        """mkdtemp PermissionError becomes RuntimeError naming whisper, with no temp dir left."""
        from knowledge_builder.processors.audio import process_audio

        before = set(Path(tempfile.gettempdir()).glob("kb-audio-*"))
        with tempfile.TemporaryDirectory() as tmp:
            _install_stub(tmp, "whisper", _stub_script("known transcript\n"))
            with patch.dict(os.environ, {"PATH": tmp}):
                with patch("tempfile.mkdtemp", side_effect=PermissionError("denied")):
                    with self.assertRaises(RuntimeError) as caught:
                        process_audio("clip.wav")
        message = str(caught.exception)
        self.assertIn("whisper", message)
        self.assertIn("audio extractor", message)
        self.assertNotIsInstance(caught.exception, PermissionError)
        after = set(Path(tempfile.gettempdir()).glob("kb-audio-*"))
        self.assertEqual(after, before)

    def test_whisper_transcript_read_oserror_raises_runtime_error_and_removes_temp_dir(self):
        """Reading the whisper .txt as OSError becomes RuntimeError, and the temp dir is removed."""
        from knowledge_builder.processors.audio import process_audio

        created = []
        real_mkdtemp = tempfile.mkdtemp

        def spy_mkdtemp(*args, **kwargs):
            path = real_mkdtemp(*args, **kwargs)
            created.append(path)
            (Path(path) / "clip.txt").write_text("hidden transcript\n", encoding="utf-8")
            return path

        with tempfile.TemporaryDirectory() as tmp:
            _install_stub(tmp, "whisper", _stub_script("printed transcript\n"))
            with patch.dict(os.environ, {"PATH": tmp}):
                with patch("tempfile.mkdtemp", side_effect=spy_mkdtemp):
                    with patch.object(Path, "read_text", side_effect=OSError("unreadable")):
                        with self.assertRaises(RuntimeError) as caught:
                            process_audio("clip.wav")
        message = str(caught.exception)
        self.assertIn("whisper", message)
        self.assertIn("audio extractor", message)
        self.assertNotIn("hidden transcript", message)
        self.assertNotIn("printed transcript", message)
        self.assertEqual(len(created), 1)
        self.assertFalse(Path(created[0]).exists())


if __name__ == "__main__":
    unittest.main()
