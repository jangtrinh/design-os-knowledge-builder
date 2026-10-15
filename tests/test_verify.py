"""P0.2 verify: knowledge-file shape, hashes, anchors, and the walk rules.

The live corpus shape (not the single-object emitter) is a list under
source_attribution and unquoted ease:source anchors. Lint only sees headings.
"""

import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


URI = "_evidence/example-run/sources/example-source.md"
REL = "example-domain/example-topic/example-tool-configuration.md"
SOURCE = b"Example tool configuration uses one setting.\n"


def _flip_nibble(digest):
    return digest[:-1] + ("0" if digest[-1] != "0" else "1")


def _run(argv):
    import knowledge_builder.cli as cli_mod

    stdout = io.StringIO()
    stderr = io.StringIO()
    with patch("sys.argv", argv), patch("sys.stdout", stdout), patch("sys.stderr", stderr):
        try:
            cli_mod.main()
            code = 0
        except SystemExit as caught:
            code = caught.code
    return code, stdout.getvalue(), stderr.getvalue()


def _knowledge(sha, uri=URI, *, anchor_sha=None, trust_tier="verified"):
    anchor_sha = sha if anchor_sha is None else anchor_sha
    return f"""---
id: example-tool-configuration
title: "Example tool configuration"
domain: "example-domain"
description: "Set one option on the example tool."
when:
  - "configure the example tool"
  - "example-option"
trust_tier: "{trust_tier}"
version: "1.0.0"
source_attribution:
  - uri: "{uri}"
    sha256: "{sha}"
---

# Example tool configuration

## Purpose

Show how to set one option on the example tool.

## When to Use / When NOT

### ALLOWED (When to Use)

- Configure the example tool.

### NOT ALLOWED (When NOT to Use)

- Do not change an unrelated setting.

## Core Knowledge Content

Example tool configuration uses one setting.
<!-- ease:source uri={uri} sha256={anchor_sha} -->

## Failure Modes (Mandatory)

1. **Example miss**: a missing option leaves the example tool unchanged.
"""


def _populate(root, text, source=SOURCE):
    src = root / URI
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(source)
    (root / "README.md").write_text("# repo readme\n\nNot a knowledge unit.\n", encoding="utf-8")
    topic = root / "example-domain" / "example-topic"
    topic.mkdir(parents=True, exist_ok=True)
    (topic / "README.md").write_text("# topic readme\n\nNot a knowledge unit.\n", encoding="utf-8")
    brief = root / "_evidence" / "example-run" / "brief.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text("# brief\n\nNot a knowledge unit.\n", encoding="utf-8")
    md = root / REL
    md.write_text(text, encoding="utf-8")
    return md


def _count(testcase, out, label):
    prefix = label + ":"
    for line in out.splitlines():
        if line.startswith(prefix):
            return int(line.split(":", 1)[1].strip())
    testcase.fail(f"missing {label} count in stdout:\n{out}")


class TestVerifyPermissionsFile(unittest.TestCase):
    def test_flipped_sha256_nibble_names_path_and_matching_hash_exits_0(self):
        """Lint ignores a flipped digest. verify exits 1 and names the path; a match exits 0."""
        digest = hashlib.sha256(SOURCE).hexdigest()
        flipped = _flip_nibble(digest)
        self.assertNotEqual(flipped, digest)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            md = _populate(root, _knowledge(flipped, anchor_sha=digest))

            lint_code, _lint_out, lint_err = _run(["knowledge-builder", "lint", str(md)])
            self.assertEqual(lint_code, 0, lint_err)

            code, out, err = _run(["knowledge-builder", "verify", str(root), "--legacy"])
            self.assertNotIn("invalid choice", err)
            self.assertEqual(code, 1)
            self.assertIn(REL, out)
            self.assertEqual(_count(self, out, "files"), 1)
            self.assertEqual(_count(self, out, "anchors"), 1)
            self.assertGreaterEqual(_count(self, out, "failures"), 1)

            _populate(root, _knowledge(digest))
            code, out, err = _run(["knowledge-builder", "verify", str(root), "--legacy"])
            self.assertEqual(code, 0, out + err)
            self.assertEqual(_count(self, out, "files"), 1)
            self.assertEqual(_count(self, out, "anchors"), 1)
            self.assertEqual(_count(self, out, "failures"), 0)

    def test_anchor_sha256_is_checked_when_frontmatter_matches(self):
        digest = hashlib.sha256(SOURCE).hexdigest()
        flipped = _flip_nibble(digest)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _populate(root, _knowledge(digest, anchor_sha=flipped))
            code, out, err = _run(["knowledge-builder", "verify", str(root), "--legacy"])
            self.assertNotIn("invalid choice", err)
            self.assertEqual(code, 1, out + err)
            self.assertIn(REL, out)
            self.assertIn(URI, out)

    def test_rejects_file_scheme_absolute_and_escaping_uris(self):
        digest = hashlib.sha256(SOURCE).hexdigest()
        cases = {
            "file-scheme": "file:///tmp/example-source.md",
            "absolute": "/etc/passwd",
            "escapes-root": "../outside.txt",
            "missing-file": "_evidence/example-run/sources/missing.md",
        }
        for name, uri in cases.items():
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    _populate(root, _knowledge(digest, uri=uri))
                    code, out, err = _run(["knowledge-builder", "verify", str(root), "--legacy"])
                    self.assertNotIn("invalid choice", err)
                    self.assertEqual(code, 1, out + err)
                    self.assertIn(REL, out)

    def test_source_attribution_must_be_a_list(self):
        """The single-object emitter shape is not the canonical schema."""
        digest = hashlib.sha256(SOURCE).hexdigest()
        text = _knowledge(digest).replace(
            f'  - uri: "{URI}"\n    sha256: "{digest}"\n',
            f'  uri: "{URI}"\n  sha256: "{digest}"\n',
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _populate(root, text)
            code, out, err = _run(["knowledge-builder", "verify", str(root), "--legacy"])
            self.assertNotIn("invalid choice", err)
            self.assertEqual(code, 1, out + err)
            self.assertIn(REL, out)

    def test_required_frontmatter_and_four_headings(self):
        digest = hashlib.sha256(SOURCE).hexdigest()
        mutations = {
            "bad-id": (
                "id: example-tool-configuration",
                "id: Not_Kebab",
            ),
            "bad-trust-tier": ('trust_tier: "verified"', 'trust_tier: "gold"'),
            "when-not-a-list": (
                'when:\n  - "configure the example tool"\n  - "example-option"\n',
                'when: "configure the example tool"\n',
            ),
            "missing-version": ('version: "1.0.0"\n', ""),
            "missing-purpose": ("## Purpose\n", "## Intent\n"),
        }
        for name, (old, new) in mutations.items():
            with self.subTest(name=name):
                text = _knowledge(digest).replace(old, new, 1)
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    _populate(root, text)
                    code, out, err = _run(["knowledge-builder", "verify", str(root), "--legacy"])
                    self.assertNotIn("invalid choice", err)
                    self.assertEqual(code, 1, out + err)
                    self.assertIn(REL, out)

    def test_draft_and_community_reference_trust_tiers_pass(self):
        digest = hashlib.sha256(SOURCE).hexdigest()
        for tier in ("draft", "community_reference"):
            with self.subTest(tier=tier):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    _populate(root, _knowledge(digest, trust_tier=tier))
                    code, out, err = _run(["knowledge-builder", "verify", str(root), "--legacy"])
                    self.assertNotIn("invalid choice", err)
                    self.assertEqual(code, 0, out + err)
                    self.assertEqual(_count(self, out, "failures"), 0)


if __name__ == "__main__":
    unittest.main()
