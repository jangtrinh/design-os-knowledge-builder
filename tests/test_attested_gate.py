"""A source counts only when the capture log matches it, and a quote must sit in the body."""

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import knowledge_builder
from knowledge_builder.ontology.actions import ActionError, run_action
from tests.pack_support import add_atom, scaffold_root, write_claim, write_source
from tests.test_ontology_support import run_cli

LONG = "Alpha holds in every case across the measured range."
SHORT = "Alpha holds."
HEADER_QUOTE = "alpha holds across the measured sample today"
RULE = "quote must be at least 6 words and 30 characters"


def _init(root):
    code, out, err = run_cli(
        ["knowledge-builder", "run", "init", "--root", str(root), "--id", "r1", "--budget", "4", "--require", "c1"]
    )
    assert code == 0, out + err
    path = root / "_evidence" / "r1" / "state.json"
    state = json.loads(path.read_text(encoding="utf-8"))
    state.update({
        "last_weighted_delta": 0.01,
        "consecutive_low_delta_rounds": 3,
        "has_viable_probe_remaining": True,
        "is_target_version_matched": True,
        "researcher_runtime": "researcher-a",
    })
    path.write_text(json.dumps(state), encoding="utf-8")


def _capture(root, stem, body, header=True):
    path = root / "_evidence" / "r1" / "sources" / f"{stem}.txt"
    if header:
        data = f"Source-URL: https://{stem}.example/page\nFetched: 2026-10-13T05:00:00+00:00\n\n{body}\n".encode()
    else:
        data = body.encode()
    path.write_bytes(data)
    rel = f"_evidence/r1/sources/{stem}.txt"
    return rel, hashlib.sha256(data).hexdigest()


def _atom(root, ident, rel, digest, quote, claim_type="FACT", extra=None):
    atom = {
        "id": ident, "run_id": "r1", "claim_type": claim_type, "statement": f"support for {ident}",
        "source_uri": rel, "source_digest": digest, "captured_at": "2026-10-13T05:00:00+00:00",
        "confidence": "HIGH", "verified_by_code": False,
        "metadata": {"claim": "c1", **(extra or {})}, "quote": quote,
    }
    with (root / "_evidence" / "r1" / "evidence.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(atom) + "\n")
    return atom


def _attest(root, rel, digest, origin="from-file", url="https://example.com/page", command=None, exit_code=None):
    row = {
        "path": rel, "sha256": digest, "origin": origin, "url": url, "command": command,
        "exit_code": exit_code, "captured_at": "2026-10-13T05:00:00+00:00",
        "tool_version": knowledge_builder.__version__,
    }
    with (root / "_evidence" / "r1" / "captures.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def _gate(root):
    return run_cli(["knowledge-builder", "gate", "--root", str(root), "--run-id", "r1"])


class AttestedGateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "root"
        self.root.mkdir()
        _init(self.root)

    def test_unattested_source_does_not_verify(self):
        rel, digest = _capture(self.root, "page", LONG)
        _atom(self.root, "a1", rel, digest, LONG)
        code, out, err = _gate(self.root)
        self.assertNotEqual(code, 0)
        self.assertIn("Missing verified claims (0/1)", out)
        self.assertIn(f"unattested sources: 1: {rel}", out)

    def _ontology(self):
        evidence = self.root / "_evidence"
        if evidence.exists():
            shutil.rmtree(evidence)
        scaffold_root(self.root)

    def test_verify_claims_names_an_unattested_capture(self):
        self._ontology()
        atom = add_atom(self.root, "a1", "page", LONG, quote=LONG)
        write_source(self.root, "s1", atom["source_uri"], atom["source_digest"])
        write_claim(self.root, "c1", "s1", atom["source_uri"], LONG, atom="a1")
        log = self.root / "_evidence" / "r1" / "captures.jsonl"
        if log.exists():
            log.unlink()
        code, out, err = run_cli(["knowledge-builder", "verify", str(self.root), "--claims"])
        self.assertNotEqual(code, 0)
        self.assertIn(atom["source_uri"], out)
        self.assertIn("unattested capture", out)
        self.assertIn("ingest --freeze", out)
        self.assertIn("run exec", out)

    def test_short_quote_does_not_verify(self):
        rel, digest = _capture(self.root, "page", SHORT)
        _atom(self.root, "a1", rel, digest, SHORT)
        _attest(self.root, rel, digest)
        code, out, err = _gate(self.root)
        self.assertIn("Missing verified claims (0/1)", out)
        self.assertNotIn("unattested sources:", out)

    def test_quote_inside_the_header_does_not_verify(self):
        path = self.root / "_evidence" / "r1" / "sources" / "page.txt"
        data = (
            f"Source-URL: https://example.com/{HEADER_QUOTE.replace(' ', '-')}\n"
            f"Note: {HEADER_QUOTE}\n"
            "Fetched: 2026-10-13T05:00:00+00:00\n"
            "\n"
            "The body discusses an unrelated topic and never repeats the header sentence.\n"
        ).encode()
        path.write_bytes(data)
        rel = "_evidence/r1/sources/page.txt"
        digest = hashlib.sha256(data).hexdigest()
        _atom(self.root, "a1", rel, digest, HEADER_QUOTE)
        _attest(self.root, rel, digest)
        code, out, err = _gate(self.root)
        self.assertIn("Missing verified claims (0/1)", out)

    def test_promote_rejects_a_short_quote(self):
        self._ontology()
        rel, digest = _capture(self.root, "page", SHORT)
        _atom(self.root, "a1", rel, digest, SHORT)
        with self.assertRaises(ActionError) as caught:
            run_action(self.root, "promote-claim", {"atom": "a1", "kind": "official"})
        self.assertIn(RULE, str(caught.exception))

    def test_promote_rejects_a_header_only_quote(self):
        self._ontology()
        atom = add_atom(self.root, "a1", "page", "The body discusses an unrelated topic in this capture.", quote=LONG)
        path = self.root / atom["source_uri"]
        text = path.read_text(encoding="utf-8")
        body, rest = text.split("\n\n", 1)
        path.write_bytes(f"{body}\nNote: {LONG}\n\nThe body discusses an unrelated topic in this capture.\n".encode())
        # digest must still match; rewrite the atom line to the new bytes
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        evidence = self.root / "_evidence" / "r1" / "evidence.jsonl"
        stored = json.loads(evidence.read_text(encoding="utf-8").splitlines()[-1])
        stored["source_digest"] = digest
        evidence.write_text(json.dumps(stored) + "\n", encoding="utf-8")
        with self.assertRaises(ActionError) as caught:
            run_action(self.root, "promote-claim", {"atom": "a1", "kind": "official"})
        self.assertIn("quote is not in the frozen file", str(caught.exception))
        self.assertNotIn(RULE, str(caught.exception))

    def test_failure_mode_needs_a_verified_quote(self):
        rel, digest = _capture(self.root, "fail", "known failure mode")
        _atom(self.root, "fm", rel, digest, "known failure mode", claim_type="FAILURE_MODE")
        _attest(self.root, rel, digest)
        code, out, err = _gate(self.root)
        self.assertIn("Counterevidence and failure modes not yet searched", out)

    def test_failure_mode_with_a_body_quote_counts(self):
        quote = "known failure mode happens when the input is empty and unchecked."
        rel, digest = _capture(self.root, "fail", quote)
        _atom(self.root, "fm", rel, digest, quote, claim_type="FAILURE_MODE")
        _attest(self.root, rel, digest)
        code, out, err = _gate(self.root)
        self.assertNotIn("Counterevidence and failure modes not yet searched", out)

    def test_command_on_a_fetched_capture_is_not_execution_proof(self):
        rel, digest = _capture(self.root, "page", LONG)
        _atom(self.root, "a1", rel, digest, LONG, extra={"command": "python3 -m unittest"})
        _attest(self.root, rel, digest, origin="fetched", url="https://page.example/page")
        code, out, err = _gate(self.root)
        self.assertIn("Missing code execution / test verification proof", out)

    def test_executed_capture_with_exit_zero_is_execution_proof(self):
        rel, digest = _capture(self.root, "page", LONG, header=False)
        command = ["python3", "-m", "unittest"]
        text = f"Command: python3 -m unittest\nExit: 0\nRan: 2026-10-13T05:00:00+00:00\n\n{LONG}\n"
        path = self.root / rel
        path.write_text(text, encoding="utf-8")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        _atom(self.root, "a1", rel, digest, LONG, extra={"command": "python3 -m unittest"})
        _attest(self.root, rel, digest, origin="executed", url=None, command=command, exit_code=0)
        code, out, err = _gate(self.root)
        self.assertNotIn("Missing code execution / test verification proof", out)

    def test_nonzero_exit_is_not_execution_proof(self):
        rel, digest = _capture(self.root, "page", LONG)
        _atom(self.root, "a1", rel, digest, LONG, extra={"command": "python3 -m unittest"})
        _attest(self.root, rel, digest, origin="executed", command=["python3", "-m", "unittest"], exit_code=3)
        code, out, err = _gate(self.root)
        self.assertIn("Missing code execution / test verification proof", out)
