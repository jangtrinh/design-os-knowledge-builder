"""P1.2 gate reads the ledger. Integer flags stay on --self-report and cannot exit 0.

Fixture: 1 of 2 frozen required ids has an atom whose source file still hashes
to source_digest. `gate --self-report --verified 2 --required 2` must not exit 0.
`gate --root --run-id` exits 2 (DEEPEN). Complete claims and exhausted budget
exit 3 (PAUSE_BUDGET).
"""

import hashlib
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


class TestGateLedger(unittest.TestCase):
    def test_self_report_verified_flags_do_not_exit_zero(self):
        """Integer flags under --self-report may print a decision and must not exit 0."""
        code, out, err = _run(
            [
                "knowledge-builder",
                "gate",
                "--self-report",
                "--verified",
                "2",
                "--required",
                "2",
            ]
        )
        self.assertNotEqual(code, 0, out + err)
        self.assertNotIn("unrecognized arguments", err)

    def test_init_freezes_required_claim_ids_and_researcher(self):
        """Repeatable --require and --researcher are frozen into state.json."""
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
                    "--require",
                    "c1",
                    "--require",
                    "c2",
                    "--researcher",
                    "grok",
                ]
            )
            self.assertEqual(code, 0, out + err)
            state = json.loads(
                (root / "_evidence" / "run-1" / "state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(state["required_claim_ids"], ["c1", "c2"])
            self.assertEqual(state["researcher_runtime"], "grok")

    def test_partial_ledger_deepens_then_exhausted_budget_pauses(self):
        """1 of 2 required ids -> exit 2. Complete claims and budget 0 -> exit 3.

        Counts come from the ledger. A stuffed independent_source_uris tally and
        integer --verified/--required flags do not.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = root / "_evidence" / "run-1"
            sources = run / "sources"
            sources.mkdir(parents=True)
            body = b"frozen claim c1\n"
            rel = "_evidence/run-1/sources/c1.txt"
            (root / rel).write_bytes(body)
            digest = _sha(body)
            atoms = [
                _atom("atom-c1", "c1", rel, digest, quote="frozen claim c1"),
                _atom(
                    "contra-1",
                    "c-extra",
                    "_evidence/run-1/sources/missing.txt",
                    "b" * 64,
                    claim_type="CONTRADICTION",
                ),
            ]
            (run / "evidence.jsonl").write_text(
                "".join(json.dumps(atom) + "\n" for atom in atoms),
                encoding="utf-8",
            )
            state = {
                "run_id": "run-1",
                "round": 0,
                "status": "RUNNING",
                "budget_used": 0,
                "budget_total": 4,
                "remaining_budget_calls": 4,
                "gaps": [],
                "resolved": [],
                "required_claim_ids": ["c1", "c2"],
                "minimum_independent_sources": 2,
                "last_weighted_delta": None,
                "researcher_runtime": "grok",
                "independent_source_uris": 41,
            }
            (run / "state.json").write_text(json.dumps(state), encoding="utf-8")

            code, out, err = _run(
                [
                    "knowledge-builder",
                    "gate",
                    "--root",
                    str(root),
                    "--run-id",
                    "run-1",
                    "--verified",
                    "2",
                    "--required",
                    "2",
                    "--sources",
                    "41",
                ]
            )
            self.assertEqual(code, 2, out + err)
            self.assertIn("DEEPEN", out)
            self.assertIn("Missing verified claims (1/2)", out)
            self.assertIn("Insufficient independent sources (1 < 2)", out)
            self.assertIn("Unresolved contradictions (1)", out)
            self.assertIn("Missing code execution / test verification proof", out)
            self.assertIn("Counterevidence and failure modes not yet searched", out)
            self.assertNotIn("41 < 2", out)

            (root / rel).write_bytes(b"tampered\n")
            code, out, err = _run(
                [
                    "knowledge-builder",
                    "gate",
                    "--root",
                    str(root),
                    "--run-id",
                    "run-1",
                ]
            )
            self.assertEqual(code, 2, out + err)
            self.assertIn("Missing verified claims (0/2)", out)

            (root / rel).write_bytes(body)
            body2 = b"frozen claim c2\n"
            rel2 = "_evidence/run-1/sources/c2.txt"
            (root / rel2).write_bytes(body2)
            atoms.append(_atom("atom-c2", "c2", rel2, _sha(body2), quote="frozen claim c2"))
            (run / "evidence.jsonl").write_text(
                "".join(json.dumps(atom) + "\n" for atom in atoms),
                encoding="utf-8",
            )
            state["remaining_budget_calls"] = 0
            (run / "state.json").write_text(json.dumps(state), encoding="utf-8")

            code, out, err = _run(
                [
                    "knowledge-builder",
                    "gate",
                    "--root",
                    str(root),
                    "--run-id",
                    "run-1",
                ]
            )
            self.assertEqual(code, 3, out + err)
            self.assertIn("PAUSE_BUDGET", out)


if __name__ == "__main__":
    unittest.main()
