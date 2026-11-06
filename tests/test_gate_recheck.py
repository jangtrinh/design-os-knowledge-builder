"""Offline, the gate trusts review.json sources. --recheck fetches the pages.

A review whose hashes match and whose sources claim every quote was found
certifies STOP_SUFFICIENT while the fetch is never called. With --recheck
the same review does not certify when the fetched page lacks the quote.
The reason names that quote. An unreachable page fails the same way.
Execution captures are not re-run. Pack check uses the same switch.
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from knowledge_builder.processors.web_freeze import FreezeError
from knowledge_builder.research.review_check import claims_digest
from tests.capture_support import append_capture
from tests.test_run_review import EXEC, FAIL_QUOTE, QUOTE, _atom, _bound_review, _finish, _init, _run, _source

ONTOLOGY = Path(__file__).resolve().parent / "fixtures" / "ontology" / "root" / "ontology.yaml"
NOTE = "note: sources were checked by the review, not now; rerun with --recheck to fetch them"
EMPTY = "<html><body><p>unrelated words without the captured sentence.</p></body></html>"
URL_A = "https://example.com/a"
URL_B = "https://example.com/b"


def _sources(rel_a, rel_b):
    return [
        {"url": URL_A, "path": rel_a, "status": "ok", "quotes_found": 1, "quotes_total": 1, "missing_atoms": []},
        {"url": URL_B, "path": rel_b, "status": "ok", "quotes_found": 1, "quotes_total": 1, "missing_atoms": []},
    ]


def _forged(root):
    """Ledger plus a hand-written review that claims both quotes were found."""
    _init(root)
    rel_a, dig_a = _source(root, "a.txt", QUOTE, URL_A)
    rel_b, dig_b = _source(root, "b.txt", FAIL_QUOTE, URL_B)
    rel_e, dig_e = _source(root, "e.txt", QUOTE, None)
    append_capture(root, rel_a, dig_a, origin="from-file", url=URL_A)
    append_capture(root, rel_b, dig_b, origin="fetched", url=URL_B)
    append_capture(root, rel_e, dig_e, origin="executed", command=EXEC, exit_code=0)
    run = _finish(
        root,
        [
            _atom("atom-c1", "a.txt", dig_a, "FACT", QUOTE),
            _atom("atom-fail", "b.txt", dig_b, "FAILURE_MODE", FAIL_QUOTE, claim="fail-1"),
            _atom("atom-exec", "e.txt", dig_e, "FACT", QUOTE, extra={"command": "python3 -m unittest"}),
        ],
    )
    shutil.copy(ONTOLOGY, Path(root) / "ontology.yaml")
    _bound_review(run, claims_sha256=claims_digest(root), sources=_sources(rel_a, rel_b))
    return run


def _gate(root, recheck=False):
    argv = ["knowledge-builder", "gate", "--root", str(root), "--run-id", "run-1"]
    if recheck:
        argv.append("--recheck")
    return _run(argv)


def _pack(root, recheck=False):
    argv = ["knowledge-builder", "pack", "check", "--root", str(root), "--run", "run-1"]
    if recheck:
        argv.append("--recheck")
    return _run(argv)


class TestGateRecheck(unittest.TestCase):
    def test_forged_review_stops_offline_and_names_the_missing_quote_on_recheck(self):
        calls = []

        def fake_fetch(url):
            calls.append(url)
            return EMPTY

        with tempfile.TemporaryDirectory() as tmp, patch(
            "knowledge_builder.research.live_sources.fetch_html", fake_fetch
        ):
            _forged(tmp)
            from knowledge_builder.research.ledger_gate import ledger_evaluation_input

            counted = ledger_evaluation_input(tmp, "run-1")
            self.assertEqual(counted.independent_sources_count, 2)
            offline = _gate(tmp)
            self.assertEqual(calls, [])
            online = _gate(tmp, recheck=True)
            fetched = list(calls)
            recounted = ledger_evaluation_input(tmp, "run-1", recheck=True)
            self.assertEqual(recounted.independent_sources_count, 1)
            before_pack = len(calls)
            pack_off = _pack(tmp)
            after_offline_pack = len(calls)
            pack_on = _pack(tmp, recheck=True)

        self.assertEqual(offline[0], 0, offline[1] + offline[2])
        self.assertIn("STOP_SUFFICIENT", offline[1])
        self.assertIn(NOTE, offline[1])
        self.assertNotIn("recheck:", offline[1])
        self.assertNotEqual(online[0], 0, online[1] + online[2])
        self.assertNotIn("STOP_SUFFICIENT", online[1])
        self.assertIn(f"quote not found on live page for atom-c1: {QUOTE}", online[1])
        self.assertIn("recheck: 2 sources fetched, 0 unreachable, 2 quotes missing", online[1])
        self.assertIn("recheck: execution captures are not re-run", online[1])
        self.assertEqual(fetched, [URL_A, URL_B])
        self.assertIn("gate: STOP_SUFFICIENT", pack_off[1])
        self.assertIn(NOTE, pack_off[1])
        self.assertEqual(after_offline_pack, before_pack)
        self.assertNotIn("gate: STOP_SUFFICIENT", pack_on[1])
        self.assertIn(f"quote not found on live page for atom-c1: {QUOTE}", pack_on[1])
        self.assertIn("recheck: 2 sources fetched, 0 unreachable, 2 quotes missing", pack_on[1])
        self.assertIn("recheck: execution captures are not re-run", pack_on[1])
        self.assertNotIn(NOTE, pack_on[1])

    def test_unreachable_source_fails_closed_like_a_missing_quote(self):
        def fake_fetch(url):
            raise FreezeError(f"could not fetch {url}")

        with tempfile.TemporaryDirectory() as tmp, patch(
            "knowledge_builder.research.live_sources.fetch_html", fake_fetch
        ):
            _forged(tmp)
            code, out, err = _gate(tmp, recheck=True)
        self.assertNotEqual(code, 0, out + err)
        self.assertNotIn("STOP_SUFFICIENT", out)
        self.assertIn(f"quote not found on live page for atom-c1: {QUOTE}", out)
        self.assertIn("recheck: 0 sources fetched, 2 unreachable, 2 quotes missing", out)
        self.assertIn("recheck: execution captures are not re-run", out)

    def test_recheck_still_requires_a_current_passing_review(self):
        def fake_fetch(url):
            return f"<html><body><p>{QUOTE} {FAIL_QUOTE}</p></body></html>"

        with tempfile.TemporaryDirectory() as tmp, patch(
            "knowledge_builder.research.live_sources.fetch_html", fake_fetch
        ):
            run = _forged(tmp)
            _bound_review(
                run,
                verdict="fail",
                claims_sha256=claims_digest(tmp),
                sources=_sources("_evidence/run-1/sources/a.txt", "_evidence/run-1/sources/b.txt"),
            )
            failed = _gate(tmp, recheck=True)
            _bound_review(
                run,
                ledger_sha256="0" * 64,
                claims_sha256=claims_digest(tmp),
                sources=_sources("_evidence/run-1/sources/a.txt", "_evidence/run-1/sources/b.txt"),
            )
            stale = _gate(tmp, recheck=True)
        self.assertNotIn("STOP_SUFFICIENT", failed[1])
        self.assertIn("Independent review has not passed", failed[1])
        self.assertIn("recheck: 2 sources fetched, 0 unreachable, 0 quotes missing", failed[1])
        self.assertNotIn("STOP_SUFFICIENT", stale[1])
        self.assertIn("review is stale: evidence.jsonl changed after review", stale[1])


if __name__ == "__main__":
    unittest.main()
