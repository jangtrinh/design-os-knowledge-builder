"""P1.3 claim-vs-source. verify --claims checks quote= against the hashed file.

The file contains "strict is read-only" and the quote is the real sentence
"strict still permits writes". verify --claims exits 1. Swap in the real
sentence and it exits 0. Default verify stays structural. A claim with no
quote is UNCHECKED and does not increment required_claims_verified.
"""

import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


URI = "_evidence/run-1/sources/note.txt"
REL = "topic/note.md"
REAL = "strict still permits writes"
WRONG = b"strict is read-only\n"


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


def _knowledge(sha, source_body, *, quote=REAL):
    quote_attr = "" if quote is None else f' quote="{quote}"'
    text = source_body.decode("utf-8")
    return f"""---
id: note
title: "Note"
domain: "topic"
description: "A sourced note."
when:
  - "checking a quote"
trust_tier: "verified"
version: "1.0.0"
source_attribution:
  - uri: "{URI}"
    sha256: "{sha}"
---

# Note

## Purpose

Record one sourced sentence.

## When to Use / When NOT

### ALLOWED (When to Use)

- Checking a quote.

### NOT ALLOWED (When NOT to Use)

- Do not invent the sentence.

## Core Knowledge Content

{text}
<!-- ease:source uri={URI} sha256={sha}{quote_attr} -->

## Failure Modes (Mandatory)

1. **Wrong sentence**: the quote is not in the hashed file.
"""


def _populate(root, source_body, *, quote=REAL):
    digest = _sha(source_body)
    src = root / URI
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(source_body)
    md = root / REL
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(_knowledge(digest, source_body, quote=quote), encoding="utf-8")
    return digest


def _count(testcase, out, label):
    prefix = label + ":"
    for line in out.splitlines():
        if line.startswith(prefix):
            return int(line.split(":", 1)[1].strip())
    testcase.fail(f"missing {label} count in stdout:\n{out}")


class TestVerifyClaims(unittest.TestCase):
    def test_wrong_sentence_fails_claims_until_the_real_sentence_is_in_the_file(self):
        """Quote must be a substring of the hashed file. Default verify stays structural."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _populate(root, WRONG)

            code, out, err = _run(["knowledge-builder", "verify", str(root)])
            self.assertNotIn("unrecognized arguments", err)
            self.assertEqual(code, 0, out + err)
            self.assertEqual(_count(self, out, "failures"), 0)

            code, out, err = _run(["knowledge-builder", "verify", "--claims", str(root)])
            self.assertNotIn("unrecognized arguments", err)
            self.assertEqual(code, 1, out + err)
            self.assertIn(REL, out)
            self.assertIn("quote", out.lower())

            _populate(root, REAL.encode("utf-8") + b"\n")
            code, out, err = _run(["knowledge-builder", "verify", "--claims", str(root)])
            self.assertNotIn("unrecognized arguments", err)
            self.assertEqual(code, 0, out + err)
            self.assertEqual(_count(self, out, "failures"), 0)

    def test_claims_normalises_newlines(self):
        """A quote that uses LF matches a hashed file that uses CRLF."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _populate(root, b"alpha\r\nbeta\r\n", quote="alpha\nbeta")
            code, out, err = _run(["knowledge-builder", "verify", "--claims", str(root)])
            self.assertNotIn("unrecognized arguments", err)
            self.assertEqual(code, 0, out + err)
            self.assertEqual(_count(self, out, "failures"), 0)

    def test_anchor_without_quote_is_unchecked(self):
        """No quote fails --claims as UNCHECKED. Structural verify still passes."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _populate(root, REAL.encode("utf-8") + b"\n", quote=None)

            code, out, err = _run(["knowledge-builder", "verify", str(root)])
            self.assertEqual(code, 0, out + err)

            code, out, err = _run(["knowledge-builder", "verify", "--claims", str(root)])
            self.assertNotIn("unrecognized arguments", err)
            self.assertEqual(code, 1, out + err)
            self.assertIn("UNCHECKED", out)
            self.assertIn(REL, out)


def _atom(atom_id, claim_id, source_uri, digest, *, quote=None):
    atom = {
        "id": atom_id,
        "run_id": "run-1",
        "claim_type": "FACT",
        "statement": claim_id,
        "source_uri": source_uri,
        "source_digest": digest,
        "captured_at": "2026-10-12T00:00:00Z",
        "confidence": "HIGH",
        "verified_by_code": False,
        "metadata": {"claim": claim_id},
    }
    if quote is not None:
        atom["quote"] = quote
    return atom


def _ledger(root, atoms, required):
    run = root / "_evidence" / "run-1"
    (run / "sources").mkdir(parents=True)
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
        "required_claim_ids": required,
        "minimum_independent_sources": 2,
        "last_weighted_delta": None,
        "researcher_runtime": "researcher-a",
    }
    (run / "state.json").write_text(json.dumps(state), encoding="utf-8")


class TestAtomQuotes(unittest.TestCase):
    def test_atom_without_quote_does_not_verify_the_claim(self):
        """A hash match with no quote is UNCHECKED and does not increment the count."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            body = b"strict still permits writes\n"
            rel = "_evidence/run-1/sources/c1.txt"
            _ledger(root, [], ["c1"])
            (root / rel).write_bytes(body)
            atoms = [_atom("atom-c1", "c1", rel, _sha(body))]
            (root / "_evidence" / "run-1" / "evidence.jsonl").write_text(
                json.dumps(atoms[0]) + "\n",
                encoding="utf-8",
            )
            code, out, err = _run(
                ["knowledge-builder", "gate", "--root", str(root), "--run-id", "run-1"]
            )
            self.assertEqual(code, 2, out + err)
            self.assertIn("Missing verified claims (0/1)", out)

    def test_atom_quote_must_be_in_the_hashed_file(self):
        """A wrong quote does not count. The real sentence does, including CRLF sources."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rel = "_evidence/run-1/sources/c1.txt"
            _ledger(root, [], ["c1"])
            (root / rel).write_bytes(WRONG)
            atoms = [_atom("atom-c1", "c1", rel, _sha(WRONG), quote=REAL)]
            evidence = root / "_evidence" / "run-1" / "evidence.jsonl"
            evidence.write_text(json.dumps(atoms[0]) + "\n", encoding="utf-8")

            code, out, err = _run(
                ["knowledge-builder", "gate", "--root", str(root), "--run-id", "run-1"]
            )
            self.assertEqual(code, 2, out + err)
            self.assertIn("Missing verified claims (0/1)", out)

            swapped = b"strict still permits writes\r\n"
            (root / rel).write_bytes(swapped)
            atoms[0]["source_digest"] = _sha(swapped)
            atoms[0]["quote"] = "strict still permits writes\n"
            evidence.write_text(json.dumps(atoms[0]) + "\n", encoding="utf-8")
            code, out, err = _run(
                ["knowledge-builder", "gate", "--root", str(root), "--run-id", "run-1"]
            )
            self.assertNotEqual(code, 0, out + err)
            self.assertNotIn("Missing verified claims", out)

    def test_record_round_trips_quote(self):
        """run record keeps an optional quote and still accepts an atom without one."""
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
            quoted = _atom(
                "atom-1",
                "c1",
                "_evidence/run-1/sources/note.txt",
                "a" * 64,
                quote=REAL,
            )
            code, out, err = _run(
                ["knowledge-builder", "run", "record", "--root", str(root), "--id", "run-1"],
                stdin=json.dumps(quoted),
            )
            self.assertEqual(code, 0, out + err)
            from knowledge_builder.research.ledger import AtomicResearchLedger

            atoms = AtomicResearchLedger("run-1", base_dir=root / "_evidence").load_atoms()
            self.assertEqual(len(atoms), 1)
            self.assertEqual(atoms[0].quote, REAL)


if __name__ == "__main__":
    unittest.main()
