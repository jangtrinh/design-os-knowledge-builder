"""Shared helpers for the ontology tests: a writable copy of the fixture root and a CLI runner."""

import hashlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.capture_support import append_capture, run_review

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "ontology" / "root"
FACT_QUOTE = "Alpha facts live here. Beta facts live here."
FAIL_QUOTE = "known failure mode happens when the input is empty and unchecked."
EXEC_ARGV = ["python3", "-m", "unittest"]


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


def make_stop_run(root, run_id="run-1"):
    """Complete a run under root/_evidence/<run_id> so the stopping gate returns STOP_SUFFICIENT.

    source.txt is a fetched capture (it counts). failure.txt is from-file and counts only
    after the review finds its quote. exec.txt is the execution proof and does not count.
    """
    run = Path(root) / "_evidence" / run_id
    sources = run / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    body_a = (sources / "source.txt").read_bytes() if (sources / "source.txt").exists() else (FACT_QUOTE + "\n").encode()
    if FACT_QUOTE.encode() not in body_a:
        body_a = (FACT_QUOTE + "\n").encode()
    (sources / "source.txt").write_bytes(body_a)
    body_b = (FAIL_QUOTE + "\n").encode()
    (sources / "failure.txt").write_bytes(body_b)
    exec_quote = "the command printed this measured line before it exited."
    body_e = (exec_quote + "\n").encode()
    (sources / "exec.txt").write_bytes(body_e)
    rel_a = f"_evidence/{run_id}/sources/source.txt"
    rel_b = f"_evidence/{run_id}/sources/failure.txt"
    rel_e = f"_evidence/{run_id}/sources/exec.txt"
    digest_a = hashlib.sha256(body_a).hexdigest()
    digest_b = hashlib.sha256(body_b).hexdigest()
    digest_e = hashlib.sha256(body_e).hexdigest()
    log = run / "captures.jsonl"
    if log.is_file() and not log.is_symlink():
        log.unlink()
    append_capture(root, rel_a, digest_a, origin="fetched", url="https://example.com/source", run=run_id)
    append_capture(root, rel_b, digest_b, origin="from-file", url="https://example.com/failure", run=run_id)
    append_capture(root, rel_e, digest_e, origin="executed", command=EXEC_ARGV, exit_code=0, run=run_id)

    def atom(ident, claim, name, digest, kind, quote, extra=None):
        return {
            "id": ident, "run_id": run_id, "claim_type": kind, "statement": f"support for {claim}",
            "source_uri": f"_evidence/{run_id}/sources/{name}", "source_digest": digest,
            "captured_at": "2026-10-12T00:00:00Z", "confidence": "HIGH", "verified_by_code": False,
            "metadata": dict({"claim": claim}, **(extra or {})), "quote": quote,
        }

    lines = [
        atom("atom-c1", "c1", "source.txt", digest_a, "FACT", FACT_QUOTE),
        atom("atom-fail", "fail-1", "failure.txt", digest_b, "FAILURE_MODE", FAIL_QUOTE),
        atom("atom-exec", "exec-1", "exec.txt", digest_e, "FACT", exec_quote, {"command": "python3 -m unittest"}),
    ]
    (run / "evidence.jsonl").write_text("".join(json.dumps(a) + "\n" for a in lines), encoding="utf-8")
    state = {
        "run_id": run_id, "round": 3, "status": "RUNNING", "budget_used": 1, "budget_total": 4,
        "remaining_budget_calls": 2, "gaps": [], "resolved": [], "required_claim_ids": ["c1"],
        "minimum_independent_sources": 2, "consecutive_low_delta_rounds": 3, "last_weighted_delta": 0.01,
        "has_viable_probe_remaining": False, "is_target_version_matched": True, "researcher_runtime": "researcher-a",
    }
    (run / "state.json").write_text(json.dumps(state), encoding="utf-8")
    run_review(root, run=run_id)
