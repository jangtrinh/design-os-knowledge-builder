"""`run review` re-fetches logged pages and the gate trusts only that bound file.

A review written by hand, a review by the researcher runtime, a stale hash,
or a quote the live page does not contain does not let the gate stop.
A from-file capture adds an independent source only after that re-fetch
finds its quotes. An executed capture never does. Declaring version or
execution not applicable also needs the review to confirm it.
"""

import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.capture_support import FETCHED, append_capture

QUOTE = "Alpha facts live here. Beta facts live here."
FAIL_QUOTE = "known failure mode happens when the input is empty and unchecked."
EXEC = ["python3", "-m", "unittest"]


def _run(argv, stdin=""):
    import knowledge_builder.cli as cli_mod

    stdout, stderr = io.StringIO(), io.StringIO()
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


def _init(root, researcher="researcher-a"):
    code, out, err = _run(
        [
            "knowledge-builder", "run", "init", "--root", str(root), "--id", "run-1",
            "--budget", "4", "--researcher", researcher, "--require", "c1",
        ]
    )
    assert code == 0, out + err
    return Path(root) / "_evidence" / "run-1"


def _source(root, name, body, url):
    path = Path(root) / "_evidence" / "run-1" / "sources" / name
    if url:
        text = f"Source-URL: {url}\nFetched: {FETCHED}\n\n{body}\n"
    else:
        text = f"Command: python3 -m unittest\nExit: 0\nRan: {FETCHED}\n\n{body}\n"
    path.write_text(text, encoding="utf-8")
    rel = f"_evidence/run-1/sources/{name}"
    return rel, hashlib.sha256(path.read_bytes()).hexdigest()


def _atom(ident, name, digest, kind, quote, claim="c1", extra=None):
    return {
        "id": ident,
        "run_id": "run-1",
        "claim_type": kind,
        "statement": f"support for {claim}",
        "source_uri": f"_evidence/run-1/sources/{name}",
        "source_digest": digest,
        "captured_at": "2026-10-12T00:00:00Z",
        "confidence": "HIGH",
        "verified_by_code": False,
        "metadata": {"claim": claim, **(extra or {})},
        "quote": quote,
    }


def _finish(root, atoms, **state_extra):
    run = Path(root) / "_evidence" / "run-1"
    (run / "evidence.jsonl").write_text("".join(json.dumps(a) + "\n" for a in atoms), encoding="utf-8")
    state = json.loads((run / "state.json").read_text(encoding="utf-8"))
    state.update(
        {
            "consecutive_low_delta_rounds": 3,
            "last_weighted_delta": 0.01,
            "has_viable_probe_remaining": False,
            "is_target_version_matched": True,
            "minimum_independent_sources": 2,
        }
    )
    state.update(state_extra)
    (run / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return run


def _gate(root):
    return _run(["knowledge-builder", "gate", "--root", str(root), "--run-id", "run-1"])


def _review(root, reviewer="reviewer-b", verdict="pass", **flags):
    argv = [
        "knowledge-builder", "run", "review", "--root", str(root), "--id", "run-1",
        "--reviewer", reviewer, "--verdict", verdict,
    ]
    if flags.get("confirm_version_na"):
        argv.append("--confirm-version-na")
    if flags.get("confirm_execution_na"):
        argv.append("--confirm-execution-na")
    return _run(argv)


def _bound_review(run, **overrides):
    """A review.json with the fields the gate requires, hashes matching the files as they are now."""
    body = {
        "reviewer_runtime": "reviewer-b",
        "verdict": "pass",
        "note": "",
        "reviewed_at": "2026-11-06T00:00:00+00:00",
        "ledger_sha256": hashlib.sha256((run / "evidence.jsonl").read_bytes()).hexdigest(),
        "captures_sha256": hashlib.sha256((run / "captures.jsonl").read_bytes()).hexdigest(),
        "claims_sha256": None,
        "confirm_version_na": False,
        "confirm_execution_na": False,
        "sources": [],
    }
    body.update(overrides)
    (run / "review.json").write_text(json.dumps(body), encoding="utf-8")
    return body


def _two_fetched(root):
    """Two fetched pages plus an executed capture. Enough to stop once a review binds them."""
    _init(root)
    rel_a, dig_a = _source(root, "a.txt", QUOTE, "https://example.com/a")
    rel_b, dig_b = _source(root, "b.txt", FAIL_QUOTE, "https://example.com/b")
    rel_e, dig_e = _source(root, "e.txt", QUOTE, None)
    append_capture(root, rel_a, dig_a, origin="fetched", url="https://example.com/a")
    append_capture(root, rel_b, dig_b, origin="fetched", url="https://example.com/b")
    append_capture(root, rel_e, dig_e, origin="executed", command=EXEC, exit_code=0)
    run = _finish(
        root,
        [
            _atom("atom-c1", "a.txt", dig_a, "FACT", QUOTE),
            _atom("atom-fail", "b.txt", dig_b, "FAILURE_MODE", FAIL_QUOTE, claim="fail-1"),
            _atom("atom-exec", "e.txt", dig_e, "FACT", QUOTE, extra={"command": "python3 -m unittest"}),
        ],
    )
    return run, rel_a, rel_b


class TestRunReview(unittest.TestCase):
    def test_review_refuses_empty_or_same_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            _init(tmp)
            empty = _review(tmp, reviewer="")
            same = _review(tmp, reviewer="researcher-a")
            padded = _review(tmp, reviewer="  researcher-a  ")
            self.assertFalse((Path(tmp) / "_evidence" / "run-1" / "review.json").exists())
        self.assertEqual(empty[0], 1, empty[1] + empty[2])
        self.assertIn("reviewer runtime must be non-empty", empty[2])
        self.assertEqual(same[0], 1, same[1] + same[2])
        self.assertIn("reviewer runtime equals the researcher runtime", same[2])
        self.assertEqual(padded[0], 1, padded[1] + padded[2])
        self.assertIn("reviewer runtime equals the researcher runtime", padded[2])

    def test_review_writes_bound_file_and_survives_unreachable(self):
        calls = []

        def fake_fetch(url):
            calls.append(url)
            from knowledge_builder.processors.web_freeze import FreezeError

            if url.endswith("/down"):
                raise FreezeError(f"could not fetch {url}")
            return f"<html><body><p>{QUOTE}</p></body></html>"

        with tempfile.TemporaryDirectory() as tmp:
            run = _init(tmp)
            rel_a, dig_a = _source(tmp, "a.txt", QUOTE, "https://example.com/a")
            rel_d, dig_d = _source(tmp, "down.txt", QUOTE, "https://example.com/down")
            rel_n, dig_n = _source(tmp, "nourl.txt", QUOTE, "https://example.com/unused")
            append_capture(tmp, rel_a, dig_a, origin="fetched", url="https://example.com/a")
            append_capture(tmp, rel_d, dig_d, origin="fetched", url="https://example.com/down")
            append_capture(tmp, rel_n, dig_n, origin="from-file", url=None)
            _finish(
                tmp,
                [
                    _atom("atom-c1", "a.txt", dig_a, "FACT", QUOTE),
                    _atom("atom-down", "down.txt", dig_d, "FACT", QUOTE, claim="other"),
                    _atom("atom-nourl", "nourl.txt", dig_n, "FACT", QUOTE, claim="other"),
                ],
            )
            before_sources = {
                name: (run / "sources" / name).read_bytes() for name in ("a.txt", "down.txt", "nourl.txt")
            }
            before_budget = json.loads((run / "state.json").read_text(encoding="utf-8"))["budget_used"]
            with patch("knowledge_builder.research.run_review.fetch_html", fake_fetch):
                code, out, err = _review(tmp, verdict="fail")
            self.assertEqual(code, 0, out + err)
            self.assertIn(f"{rel_a} ok quotes 1/1", out)
            self.assertIn(f"{rel_d} unreachable quotes 0/1", out)
            self.assertIn(f"{rel_n} unreachable quotes 0/1", out)
            self.assertNotIn("https://example.com/unused", calls)
            self.assertEqual(calls.count("https://example.com/down"), 1)
            written = json.loads((run / "review.json").read_text(encoding="utf-8"))
            self.assertEqual(written["verdict"], "fail")
            self.assertEqual(written["reviewer_runtime"], "reviewer-b")
            self.assertEqual(written["note"], "")
            self.assertEqual(written["ledger_sha256"], hashlib.sha256((run / "evidence.jsonl").read_bytes()).hexdigest())
            self.assertEqual(written["captures_sha256"], hashlib.sha256((run / "captures.jsonl").read_bytes()).hexdigest())
            self.assertIsNone(written["claims_sha256"])
            self.assertIs(written["confirm_version_na"], False)
            self.assertIs(written["confirm_execution_na"], False)
            self.assertEqual([row["status"] for row in written["sources"]], ["ok", "unreachable", "unreachable"])
            self.assertEqual(written["sources"][1]["missing_atoms"], ["atom-down"])
            self.assertEqual(
                {name: (run / "sources" / name).read_bytes() for name in before_sources},
                before_sources,
            )
            self.assertEqual(json.loads((run / "state.json").read_text(encoding="utf-8"))["budget_used"], before_budget)

    def test_hand_written_review_without_bound_fields_does_not_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, _rel_a, _rel_b = _two_fetched(tmp)
            (run / "review.json").write_text(
                json.dumps({"passed": True, "reviewer_runtime": "reviewer-b"}),
                encoding="utf-8",
            )
            code, out, err = _gate(tmp)
        self.assertNotEqual(code, 0, out + err)
        self.assertNotIn("STOP_SUFFICIENT", out)
        self.assertIn("Independent review has not passed", out)

    def test_stale_ledger_names_evidence_and_missing_quote_names_the_atom(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, rel_a, rel_b = _two_fetched(tmp)
            _bound_review(
                run,
                ledger_sha256="0" * 64,
                sources=[
                    {"url": "https://example.com/a", "path": rel_a, "status": "ok", "quotes_found": 1, "quotes_total": 1, "missing_atoms": []},
                    {"url": "https://example.com/b", "path": rel_b, "status": "ok", "quotes_found": 1, "quotes_total": 1, "missing_atoms": []},
                ],
            )
            _code, stale_out, stale_err = _gate(tmp)
            self.assertIn("review is stale: evidence.jsonl changed after review", stale_out + stale_err)
            _bound_review(
                run,
                sources=[
                    {"url": "https://example.com/a", "path": rel_a, "status": "ok", "quotes_found": 0, "quotes_total": 1, "missing_atoms": ["atom-c1"]},
                    {"url": "https://example.com/b", "path": rel_b, "status": "ok", "quotes_found": 1, "quotes_total": 1, "missing_atoms": []},
                ],
            )
            _code, missing_out, missing_err = _gate(tmp)
        self.assertIn("quote not found on live page for atom-c1", missing_out + missing_err)
        self.assertNotIn("STOP_SUFFICIENT", missing_out)

    def test_from_file_needs_a_live_quote_and_executed_adds_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            _init(tmp)
            rel_a, dig_a = _source(tmp, "a.txt", QUOTE, "https://example.com/a")
            rel_b, dig_b = _source(tmp, "b.txt", FAIL_QUOTE, "https://example.com/b")
            rel_e, dig_e = _source(tmp, "e.txt", QUOTE, None)
            append_capture(tmp, rel_a, dig_a, origin="fetched", url="https://example.com/a")
            append_capture(tmp, rel_b, dig_b, origin="from-file", url="https://example.com/b")
            append_capture(tmp, rel_e, dig_e, origin="executed", command=EXEC, exit_code=0)
            _finish(
                tmp,
                [
                    _atom("atom-c1", "a.txt", dig_a, "FACT", QUOTE),
                    _atom("atom-fail", "b.txt", dig_b, "FAILURE_MODE", FAIL_QUOTE, claim="fail-1"),
                    _atom("atom-exec", "e.txt", dig_e, "FACT", QUOTE, extra={"command": "python3 -m unittest"}),
                ],
            )
            from knowledge_builder.research.ledger_gate import ledger_evaluation_input

            before = ledger_evaluation_input(tmp, "run-1")
            self.assertEqual(before.independent_sources_count, 1)
            self.assertTrue(before.has_execution_proof)

            def fake_fetch(url):
                body = QUOTE if url.endswith("/a") else FAIL_QUOTE
                return f"<html><body><p>{body}</p></body></html>"

            with patch("knowledge_builder.research.run_review.fetch_html", fake_fetch):
                code, out, err = _review(tmp)
            self.assertEqual(code, 0, out + err)
            after = ledger_evaluation_input(tmp, "run-1")
        self.assertEqual(after.independent_sources_count, 2)
        self.assertTrue(after.independent_review_passed)

    def test_version_not_applicable_needs_review_confirm(self):
        from knowledge_builder.research.stopping_gate import TerminationState, evaluate_stopping_gate
        from tests.test_stopping_gate import _passing

        denied = evaluate_stopping_gate(
            _passing(version_not_applicable=True, version_reason="concept pack", is_target_version_matched=False)
        )
        self.assertNotEqual(denied.state, TerminationState.STOP_SUFFICIENT)
        self.assertIn("Version declared not applicable but the review did not confirm it", denied.reason)
        allowed = evaluate_stopping_gate(
            _passing(
                version_not_applicable=True,
                version_reason="concept pack",
                is_target_version_matched=False,
                version_na_confirmed=True,
            )
        )
        self.assertEqual(allowed.state, TerminationState.STOP_SUFFICIENT)

    def test_execution_not_applicable_needs_review_confirm(self):
        from knowledge_builder.research.stopping_gate import TerminationState, evaluate_stopping_gate
        from tests.test_stopping_gate import _passing

        denied = evaluate_stopping_gate(
            _passing(has_execution_proof=False, execution_not_applicable=True, execution_reason="no code")
        )
        self.assertNotEqual(denied.state, TerminationState.STOP_SUFFICIENT)
        self.assertIn("Execution declared not applicable but the review did not confirm it", denied.reason)
        allowed = evaluate_stopping_gate(
            _passing(
                has_execution_proof=False,
                execution_not_applicable=True,
                execution_reason="no code",
                execution_na_confirmed=True,
            )
        )
        self.assertEqual(allowed.state, TerminationState.STOP_SUFFICIENT)
