"""B6: a quote that contains a double quote uses the single-quoted attribute form.

`quote='He said "go" twice.'` is checked by verify --claims, counted by
`run measure --material`, and verified by the gate from the ledger atom. A
quote that holds both quote characters cannot be written in either form; verify
reports a malformed anchor instead of passing it.
"""

import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

URI = "_evidence/run-1/sources/talk.txt"
QUOTE = 'He said "go" twice.'
SOURCE = f"Preface line.\n{QUOTE}\nClosing line.\n".encode("utf-8")


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


def _module(digest, attr):
    return f"""---
id: talk
title: "Talk"
domain: "topic"
description: "A quoted talk."
when:
  - "quoting"
trust_tier: "verified"
version: "1.0.0"
source_attribution:
  - uri: "{URI}"
    sha256: "{digest}"
---

# Talk

## Purpose

Record a quote.

## When to Use / When NOT

Use it for quotes.

## Core Knowledge Content

The speaker was emphatic. <!-- ease:source uri={URI} sha256={digest} {attr} -->

## Failure Modes

1. A quote with a double quote must still verify.
"""


def _root(tmp, attr):
    root = Path(tmp)
    (root / URI).parent.mkdir(parents=True)
    (root / URI).write_bytes(SOURCE)
    (root / "talk.md").write_text(_module(_sha(SOURCE), attr), encoding="utf-8")
    return root


class TestQuoteWithDoubleQuote(unittest.TestCase):
    def test_single_quoted_form_passes_verify_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _root(tmp, f"quote='{QUOTE}'")
            code, out, err = _run(["knowledge-builder", "verify", "--claims", str(root)])
        self.assertEqual(code, 0, out + err)
        self.assertIn("failures: 0", out)

    def test_double_quoted_form_cannot_hold_the_quote(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _root(tmp, f'quote="{QUOTE}"')
            code, out, err = _run(["knowledge-builder", "verify", "--claims", str(root)])
        self.assertNotEqual(code, 0, out + err)
        self.assertIn("malformed ease:source anchor", out)

    def test_a_quote_with_both_quote_characters_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _root(tmp, "quote='It\\'s \"go\"'")
            code, out, err = _run(["knowledge-builder", "verify", "--claims", str(root)])
        self.assertNotEqual(code, 0, out + err)

    def test_wrong_single_quoted_quote_is_still_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _root(tmp, "quote='He said \"stop\" twice.'")
            code, out, err = _run(["knowledge-builder", "verify", "--claims", str(root)])
        self.assertNotEqual(code, 0, out + err)
        self.assertIn("quote is not in the hashed file", out)

    def test_measure_material_counts_the_single_quoted_anchor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _root(tmp, f"quote='{QUOTE}'")
            init = ["knowledge-builder", "run", "init", "--root", str(root), "--id", "run-1", "--budget", "3"]
            self.assertEqual(_run(init)[0], 0)
            base = {
                "run_id": "run-1", "claim_type": "FACT", "statement": "s", "source_uri": URI,
                "source_digest": _sha(SOURCE), "captured_at": "2026-10-13T00:00:00Z",
                "confidence": "HIGH", "verified_by_code": False,
            }
            atoms = [
                dict(base, id="a1", metadata={"round": 1}, quote="Preface line."),
                dict(base, id="a2", metadata={"round": 2, "novel": True}, quote=QUOTE),
            ]
            for atom in atoms:
                code, out, err = _run(
                    ["knowledge-builder", "run", "record", "--root", str(root), "--id", "run-1"],
                    stdin=json.dumps(atom),
                )
                self.assertEqual(code, 0, out + err)
            code, out, err = _run(
                ["knowledge-builder", "run", "measure", "--root", str(root), "--id", "run-1", "--material"]
            )
        self.assertEqual(code, 0, out + err)
        self.assertIn("round 2: atoms 1, novel 1, before 1, delta 1.0000", out)

    def test_gate_verifies_the_claim_from_the_ledger_atom(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _root(tmp, f"quote='{QUOTE}'")
            init = ["knowledge-builder", "run", "init", "--root", str(root), "--id", "run-1",
                    "--budget", "3", "--require", "talk-claim"]
            self.assertEqual(_run(init)[0], 0)
            atom = {
                "id": "a1", "run_id": "run-1", "claim_type": "FACT", "statement": "s",
                "source_uri": URI, "source_digest": _sha(SOURCE),
                "captured_at": "2026-10-13T00:00:00Z", "confidence": "HIGH",
                "verified_by_code": False, "metadata": {"claim": "talk-claim"}, "quote": QUOTE,
            }
            code, out, err = _run(
                ["knowledge-builder", "run", "record", "--root", str(root), "--id", "run-1"],
                stdin=json.dumps(atom),
            )
            self.assertEqual(code, 0, out + err)
            code, out, err = _run(["knowledge-builder", "gate", "--root", str(root), "--run-id", "run-1"])
            self.assertNotIn("Missing verified claims", out)
            # Control: the same gate reports the claim missing once the source changes.
            (root / URI).write_bytes(b"He said stop twice.\n")
            code, out, err = _run(["knowledge-builder", "gate", "--root", str(root), "--run-id", "run-1"])
        self.assertIn("Missing verified claims (0/1)", out)


if __name__ == "__main__":
    unittest.main()
