"""Reproductions for the 13 findings in review-codex-p1-9.

Each test uses the review's input. A symlink is created with os.symlink.
Negative cases start from a ledger or document that would otherwise pass.
"""

import hashlib
import io
import json
import os
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


def _sha(body):
    return hashlib.sha256(body).hexdigest()


def _atom(atom_id, claim_id, source_uri, digest, *, claim_type="FACT", metadata=None, quote=None, run_id="run-1"):
    meta = {"claim": claim_id}
    if metadata:
        meta.update(metadata)
    atom = {
        "id": atom_id,
        "run_id": run_id,
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


def _sufficient_state(**overrides):
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
    state.update(overrides)
    return state


def _write_sufficient(root, *, alias=False):
    """Two hashed sources, a passing review, and a ledger that stops today."""
    run = root / "_evidence" / "run-1"
    sources = run / "sources"
    sources.mkdir(parents=True)
    body_a = b"claim alpha holds\nknown failure mode\n"
    body_b = b"known failure mode\n"
    rel_a = "_evidence/run-1/sources/a.txt"
    rel_b = "_evidence/run-1/sources/b.txt"
    (root / rel_a).write_bytes(body_a)
    if alias:
        os.symlink("a.txt", root / rel_b)
        digest_b = _sha(body_a)
        quote_b = "known failure mode"
    else:
        (root / rel_b).write_bytes(body_b)
        digest_b = _sha(body_b)
        quote_b = "known failure mode"
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
        digest_b,
        claim_type="FAILURE_MODE",
        quote=quote_b,
    )
    (run / "evidence.jsonl").write_text(
        json.dumps(claim) + "\n" + json.dumps(failure) + "\n",
        encoding="utf-8",
    )
    (run / "state.json").write_text(json.dumps(_sufficient_state()), encoding="utf-8")
    (run / "review.json").write_text(
        json.dumps({"passed": True, "reviewer_runtime": "codex"}),
        encoding="utf-8",
    )
    return run


def _gate(root):
    return _run(["knowledge-builder", "gate", "--root", str(root), "--run-id", "run-1"])


NOTE = """---
id: note
title: "A note"
---

# Note

Body.
"""


def _knowledge(sha, uri, *, anchor_line, ident="note", trust_line='trust_tier: "verified"'):
    return f"""---
id: {ident}
title: "A note"
domain: "topic"
description: "A sourced note."
when:
  - "checking a quote"
{trust_line}
version: "1.0.0"
source_attribution:
  - uri: "{uri}"
    sha256: "{sha}"
---

# Note

## Purpose

Record one sourced sentence.

## When to Use / When NOT

Use it when the sentence is in the file.

## Core Knowledge Content

He said "no".
{anchor_line}

## Failure Modes

1. A truncated quote must not count.
"""


class TestReviewFindings(unittest.TestCase):
    def test_f01_ledger_writes_do_not_escape_the_run_directory(self):
        """_evidence symlink, evidence.jsonl symlink, and state.json symlink stay inside."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            os.symlink(outside, root / "_evidence")
            code, out, err = _run(
                ["knowledge-builder", "run", "init", "--root", str(root), "--id", "run-1", "--budget", "4"]
            )
            self.assertNotEqual(code, 0, out + err)
            self.assertFalse((outside / "run-1" / "evidence.jsonl").exists())
            self.assertFalse((outside / "run-1" / "state.json").exists())

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            code, out, err = _run(
                ["knowledge-builder", "run", "init", "--root", str(root), "--id", "run-1", "--budget", "4"]
            )
            self.assertEqual(code, 0, out + err)
            evidence = root / "_evidence" / "run-1" / "evidence.jsonl"
            outside_evidence = outside / "evidence.jsonl"
            outside_evidence.write_text("KEEP\n", encoding="utf-8")
            evidence.unlink()
            os.symlink(outside_evidence, evidence)
            atom = _atom("atom-1", "c1", "_evidence/run-1/sources/a.txt", "a" * 64, quote="keep")
            code, out, err = _run(
                ["knowledge-builder", "run", "record", "--root", str(root), "--id", "run-1"],
                stdin=json.dumps(atom),
            )
            self.assertNotEqual(code, 0, out + err)
            self.assertEqual(outside_evidence.read_text(encoding="utf-8"), "KEEP\n")

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            code, out, err = _run(
                ["knowledge-builder", "run", "init", "--root", str(root), "--id", "run-1", "--budget", "4"]
            )
            self.assertEqual(code, 0, out + err)
            state = root / "_evidence" / "run-1" / "state.json"
            outside_state = outside / "state.json"
            outside_state.write_text("SECRET", encoding="utf-8")
            state.unlink()
            os.symlink(outside_state, state)
            from knowledge_builder.research.ledger import AtomicResearchLedger

            ledger = AtomicResearchLedger("run-1", base_dir=root / "_evidence")
            with self.assertRaises(Exception):
                ledger.save_state({"run_id": "run-1"})
            self.assertTrue(os.path.islink(state))
            self.assertEqual(outside_state.read_text(encoding="utf-8"), "SECRET")

    def test_f02_unknown_version_or_probe_state_cannot_stop(self):
        """Missing booleans, and probe status "true", must not certify."""
        variants = (
            "drop-version",
            "drop-probe",
            "probe-string",
        )
        for name in variants:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    run = _write_sufficient(root)
                    code, out, err = _gate(root)
                    self.assertEqual(code, 0, out + err)
                    state = json.loads((run / "state.json").read_text(encoding="utf-8"))
                    if name == "drop-version":
                        state.pop("is_target_version_matched")
                    elif name == "drop-probe":
                        state.pop("has_viable_probe_remaining")
                    else:
                        state["has_viable_probe_remaining"] = "true"
                    (run / "state.json").write_text(json.dumps(state), encoding="utf-8")
                    code, out, err = _gate(root)
                    self.assertNotEqual(code, 0, out + err)
                    self.assertNotIn("STOP_SUFFICIENT", out)

    def test_f03_index_symlink_does_not_overwrite_an_outside_file(self):
        """index.json -> /outside/target.json must not be opened for writing."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            target = outside / "target.json"
            target.write_text("ORIGINAL", encoding="utf-8")
            os.symlink(target, root / "index.json")
            (root / "note.md").write_text(NOTE, encoding="utf-8")
            code, out, err = _run(["knowledge-builder", "index", "--root", str(root)])
            self.assertNotEqual(code, 0, out + err)
            self.assertEqual(target.read_text(encoding="utf-8"), "ORIGINAL")
            self.assertTrue(os.path.islink(root / "index.json"))

    def test_f04_source_alias_does_not_inflate_independence(self):
        """sources/b.txt -> sources/a.txt is one file, not two independent sources."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_sufficient(root, alias=True)
            code, out, err = _gate(root)
            self.assertNotEqual(code, 0, out + err)
            self.assertNotIn("STOP_SUFFICIENT", out)
            self.assertIn("1 < 2", out)

    def test_f05_malformed_required_ids_and_delta_cannot_stop(self):
        """A non-string required id, a negative delta, and -Infinity must not certify."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = _write_sufficient(root)
            state = json.loads((run / "state.json").read_text(encoding="utf-8"))
            state["required_claim_ids"] = ["c1", {"id": "unverified-c2"}]
            (run / "state.json").write_text(json.dumps(state), encoding="utf-8")
            code, out, err = _gate(root)
            self.assertNotEqual(code, 0, out + err)
            self.assertNotIn("STOP_SUFFICIENT", out)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = _write_sufficient(root)
            for raw in ("-1", "-Infinity"):
                with self.subTest(delta=raw):
                    text = (run / "state.json").read_text(encoding="utf-8")
                    text = text.replace("0.01", raw, 1)
                    (run / "state.json").write_text(text, encoding="utf-8")
                    code, out, err = _gate(root)
                    self.assertNotEqual(code, 0, out + err)
                    self.assertNotIn("STOP_SUFFICIENT", out)
                    (run / "state.json").write_text(
                        json.dumps(_sufficient_state()),
                        encoding="utf-8",
                    )

    def test_f06_frozen_source_minimum_is_enforced(self):
        """minimum_independent_sources=3 with two files must not exit 0."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = _write_sufficient(root)
            code, out, err = _gate(root)
            self.assertEqual(code, 0, out + err)
            state = json.loads((run / "state.json").read_text(encoding="utf-8"))
            state["minimum_independent_sources"] = 3
            (run / "state.json").write_text(json.dumps(state), encoding="utf-8")
            code, out, err = _gate(root)
            self.assertNotEqual(code, 0, out + err)
            self.assertNotIn("STOP_SUFFICIENT", out)
            self.assertIn("2 < 3", out)

            state["minimum_independent_sources"] = "3"
            (run / "state.json").write_text(json.dumps(state), encoding="utf-8")
            code, out, err = _gate(root)
            self.assertNotEqual(code, 0, out + err)
            self.assertNotIn("STOP_SUFFICIENT", out)

    def test_f07_atom_identity_and_claim_type_are_checked(self):
        """Wrong run_id, disallowed claim_type, and a bad record are not verified."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = _write_sufficient(root)
            evidence = run / "evidence.jsonl"
            lines = [json.loads(line) for line in evidence.read_text(encoding="utf-8").splitlines() if line.strip()]
            lines[0]["run_id"] = "run-other"
            evidence.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
            code, out, err = _gate(root)
            self.assertNotEqual(code, 0, out + err)
            self.assertNotIn("STOP_SUFFICIENT", out)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = _write_sufficient(root)
            evidence = run / "evidence.jsonl"
            lines = [json.loads(line) for line in evidence.read_text(encoding="utf-8").splitlines() if line.strip()]
            lines[0]["claim_type"] = "NOT_A_CLAIM"
            evidence.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
            code, out, err = _gate(root)
            self.assertNotEqual(code, 0, out + err)
            self.assertNotIn("STOP_SUFFICIENT", out)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = _write_sufficient(root)
            evidence = run / "evidence.jsonl"
            lines = [json.loads(line) for line in evidence.read_text(encoding="utf-8").splitlines() if line.strip()]
            bogus = _atom(
                "atom-odd",
                "odd",
                "_evidence/run-1/sources/a.txt",
                lines[0]["source_digest"],
                claim_type="NOT_A_CONTRADICTION",
                quote="claim alpha holds",
            )
            lines.append(bogus)
            evidence.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
            code, out, err = _gate(root)
            self.assertNotEqual(code, 0, out + err)
            self.assertNotIn("STOP_SUFFICIENT", out)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code, out, err = _run(
                ["knowledge-builder", "run", "init", "--root", str(root), "--id", "run-1", "--budget", "4"]
            )
            self.assertEqual(code, 0, out + err)
            evidence = root / "_evidence" / "run-1" / "evidence.jsonl"
            before = evidence.read_bytes()
            bad = _atom("atom-1", "c1", "_evidence/run-1/sources/a.txt", "a" * 64, claim_type="NOT_A_CLAIM")
            code, out, err = _run(
                ["knowledge-builder", "run", "record", "--root", str(root), "--id", "run-1"],
                stdin=json.dumps(bad),
            )
            self.assertNotEqual(code, 0, out + err)
            self.assertEqual(evidence.read_bytes(), before)
            wrong_run = _atom(
                "atom-1",
                "c1",
                "_evidence/run-1/sources/a.txt",
                "a" * 64,
                run_id="run-other",
            )
            code, out, err = _run(
                ["knowledge-builder", "run", "record", "--root", str(root), "--id", "run-1"],
                stdin=json.dumps(wrong_run),
            )
            self.assertNotEqual(code, 0, out + err)
            self.assertEqual(evidence.read_bytes(), before)

    def test_f08_symlinked_review_is_not_accepted(self):
        """review.json -> /outside/old-review.json must not certify this run."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            run = _write_sufficient(root)
            code, out, err = _gate(root)
            self.assertEqual(code, 0, out + err)
            outside_review = outside / "old-review.json"
            outside_review.write_text(
                json.dumps({"passed": True, "reviewer_runtime": "codex"}),
                encoding="utf-8",
            )
            review = run / "review.json"
            review.unlink()
            os.symlink(outside_review, review)
            code, out, err = _gate(root)
            self.assertNotEqual(code, 0, out + err)
            self.assertNotIn("STOP_SUFFICIENT", out)

    def test_f09_claims_mode_rejects_zero_anchors_and_uncited_core(self):
        """No anchors plus an unsupported sentence is not a successful claim check."""
        uri = "_evidence/run-1/sources/note.txt"
        source = b'He said "no".\n'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / uri
            src.parent.mkdir(parents=True)
            src.write_bytes(source)
            text = _knowledge(_sha(source), uri, anchor_line="")
            self.assertNotIn("ease:source", text)
            md = root / "note.md"
            md.write_text(text, encoding="utf-8")
            code, out, err = _run(["knowledge-builder", "verify", str(root)])
            self.assertEqual(code, 0, out + err)
            code, out, err = _run(["knowledge-builder", "verify", "--claims", str(root)])
            self.assertNotEqual(code, 0, out + err)
            self.assertIn("anchors: 0", out)
            self.assertNotIn("failures: 0", out)
            self.assertIn("uncited", out.lower())

    def test_f10_malformed_quote_attributes_do_not_match_a_prefix(self):
        """Truncated quotes and duplicate quote attributes are rejected."""
        uri = "_evidence/run-1/sources/note.txt"
        source = b'He said "no".\n'
        cases = {
            "truncated": '<!-- ease:source uri={uri} sha256={sha} quote="He said "yes"." -->',
            "duplicate": '<!-- ease:source uri={uri} sha256={sha} quote="no" quote="He said "no"." -->',
        }
        for name, template in cases.items():
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    src = root / uri
                    src.parent.mkdir(parents=True)
                    src.write_bytes(source)
                    digest = _sha(source)
                    anchor = template.format(uri=uri, sha=digest)
                    (root / "note.md").write_text(
                        _knowledge(digest, uri, anchor_line=anchor),
                        encoding="utf-8",
                    )
                    code, out, err = _run(["knowledge-builder", "verify", "--claims", str(root)])
                    self.assertNotEqual(code, 0, out + err)
                    self.assertNotIn("failures: 0", out)

    def test_f11_id_tier_must_be_strings_and_headings_must_be_real(self):
        """id: [] and trust_tier: [] fail. Headings inside a comment or fence do not count."""
        uri = "_evidence/run-1/sources/note.txt"
        source = b'He said "no".\n'
        digest_holder = {}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / uri
            src.parent.mkdir(parents=True)
            src.write_bytes(source)
            digest = _sha(source)
            digest_holder["sha"] = digest
            anchor = f"<!-- ease:source uri={uri} sha256={digest} -->"
            text = _knowledge(digest, uri, anchor_line=anchor)
            text = text.replace("id: note\n", "id: []\n", 1)
            (root / "note.md").write_text(text, encoding="utf-8")
            code, out, err = _run(["knowledge-builder", "verify", str(root)])
            self.assertNotEqual(code, 0, out + err)
            self.assertIn("id", out.lower())

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / uri
            src.parent.mkdir(parents=True)
            src.write_bytes(source)
            digest = _sha(source)
            anchor = f"<!-- ease:source uri={uri} sha256={digest} -->"
            text = _knowledge(digest, uri, anchor_line=anchor, trust_line="trust_tier: []")
            (root / "note.md").write_text(text, encoding="utf-8")
            code, out, err = _run(["knowledge-builder", "verify", str(root)])
            self.assertNotEqual(code, 0, out + err)
            self.assertIn("trust_tier", out)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / uri
            src.parent.mkdir(parents=True)
            src.write_bytes(source)
            digest = _sha(source)
            anchor = f"<!-- ease:source uri={uri} sha256={digest} -->"
            commented = _knowledge(digest, uri, anchor_line=anchor)
            for heading in (
                "## Purpose",
                "## When to Use / When NOT",
                "## Core Knowledge Content",
                "## Failure Modes",
            ):
                commented = commented.replace(heading, f"<!-- {heading} -->", 1)
            (root / "note.md").write_text(commented, encoding="utf-8")
            code, out, err = _run(["knowledge-builder", "verify", str(root)])
            self.assertNotEqual(code, 0, out + err)
            self.assertIn("heading", out.lower())

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / uri
            src.parent.mkdir(parents=True)
            src.write_bytes(source)
            digest = _sha(source)
            anchor = f"<!-- ease:source uri={uri} sha256={digest} -->"
            fenced = _knowledge(digest, uri, anchor_line=anchor)
            fenced = fenced.replace("## Purpose", "```\n## Purpose", 1)
            fenced = fenced.replace("## Failure Modes", "## Failure Modes\n```", 1)
            (root / "note.md").write_text(fenced, encoding="utf-8")
            code, out, err = _run(["knowledge-builder", "verify", str(root)])
            self.assertNotEqual(code, 0, out + err)
            self.assertIn("heading", out.lower())

    def test_f12_markdown_symlink_outside_the_root_is_rejected(self):
        """note.md -> /outside/note.md is not verified or indexed as a local file."""
        uri = "_evidence/run-1/sources/note.txt"
        source = b'He said "no".\n'
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            src = root / uri
            src.parent.mkdir(parents=True)
            src.write_bytes(source)
            digest = _sha(source)
            anchor = f"<!-- ease:source uri={uri} sha256={digest} -->"
            outside_note = outside / "note.md"
            outside_note.write_text(_knowledge(digest, uri, anchor_line=anchor), encoding="utf-8")
            os.symlink(outside_note, root / "note.md")
            code, out, err = _run(["knowledge-builder", "verify", str(root)])
            self.assertNotEqual(code, 0, out + err)
            self.assertNotIn("failures: 0", out)

            (root / "note.md").unlink()
            index_note = outside / "index-note.md"
            index_note.write_text(NOTE, encoding="utf-8")
            os.symlink(index_note, root / "note.md")
            code, out, err = _run(["knowledge-builder", "index", "--root", str(root)])
            self.assertNotEqual(code, 0, out + err)
            self.assertFalse((root / "index.json").exists())


if __name__ == "__main__":
    unittest.main()
