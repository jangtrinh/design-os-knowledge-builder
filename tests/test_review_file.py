"""P1.4 review.json is a separate duty.

A full ledger with no review.json does not exit 0. The same
reviewer_runtime as state.researcher_runtime does not exit 0.
A different runtime and passed true exits 0 when the other gates hold.
A missing researcher_runtime cannot prove that separation.
Required atoms still count only when their quote matches the file.
"""

import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def _run(argv):
    import knowledge_builder.cli as cli_mod

    stdout = io.StringIO()
    stderr = io.StringIO()
    with (
        patch("sys.argv", argv),
        patch("sys.stdout", stdout),
        patch("sys.stderr", stderr),
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


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


class TestReviewFileSeparateDuty(unittest.TestCase):
    def test_full_ledger_review_file_separates_duty(self):
        """No review.json, then the same runtime, then a real separate pass.

        Missing state.researcher_runtime stays non-zero. A claim atom whose
        quote does not match the hashed file stays non-zero.
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
            evidence = run / "evidence.jsonl"
            evidence.write_text(
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
                "researcher_runtime": "researcher-a",
            }
            state_path = run / "state.json"
            _write_json(state_path, state)
            review_path = run / "review.json"
            argv = [
                "knowledge-builder",
                "gate",
                "--root",
                str(root),
                "--run-id",
                "run-1",
            ]

            code, out, err = _run(argv)
            self.assertNotEqual(code, 0, out + err)
            self.assertNotIn("STOP_SUFFICIENT", out)

            _write_json(review_path, {"passed": True, "reviewer_runtime": "researcher-a"})
            code, out, err = _run(argv)
            self.assertNotEqual(code, 0, out + err)
            self.assertNotIn("STOP_SUFFICIENT", out)

            _write_json(review_path, {"passed": False, "reviewer_runtime": "reviewer-b"})
            code, out, err = _run(argv)
            self.assertNotEqual(code, 0, out + err)
            self.assertNotIn("STOP_SUFFICIENT", out)

            _write_json(review_path, {"passed": True, "reviewer_runtime": "reviewer-b"})
            code, out, err = _run(argv)
            self.assertEqual(code, 0, out + err)
            self.assertIn("STOP_SUFFICIENT", out)
            self.assertIn("independent review passed", out)

            state.pop("researcher_runtime")
            _write_json(state_path, state)
            code, out, err = _run(argv)
            self.assertNotEqual(code, 0, out + err)
            self.assertNotIn("STOP_SUFFICIENT", out)

            claim.pop("quote")
            evidence.write_text(
                json.dumps(claim) + "\n" + json.dumps(failure) + "\n",
                encoding="utf-8",
            )
            state["researcher_runtime"] = "researcher-a"
            _write_json(state_path, state)
            code, out, err = _run(argv)
            self.assertNotEqual(code, 0, out + err)
            self.assertNotIn("STOP_SUFFICIENT", out)


if __name__ == "__main__":
    unittest.main()
