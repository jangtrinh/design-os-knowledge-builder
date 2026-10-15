"""verify --claims cites each Core Knowledge block, not the whole section.

A block is a paragraph, one list item, a markdown table, or a fenced code
block. An ease:source anchor inside the block, or on the lines after it and
before the next block, cites it. Derived, Decision, and Observed
labels are exempt.
"""

import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


URI = "_evidence/run-1/sources/note.txt"
REL = "topic/note.md"
SOURCE = b"alpha holds in the file.\n"
QUOTE = "alpha holds in the file."


def _run(argv):
    import knowledge_builder.cli as cli_mod

    stdout = io.StringIO()
    stderr = io.StringIO()
    with patch("sys.argv", argv), patch("sys.stdout", stdout), patch("sys.stderr", stderr):
        try:
            cli_mod.main()
            code = 0
        except SystemExit as caught:
            code = caught.code if isinstance(caught.code, int) else 1
    return code, stdout.getvalue(), stderr.getvalue()


def _sha(body):
    return hashlib.sha256(body).hexdigest()


def _anchor(digest):
    return f'<!-- ease:source uri={URI} sha256={digest} quote="{QUOTE}" -->'


def _document(digest, core):
    if not core.endswith("\n"):
        core += "\n"
    return f"""---
id: note
title: "Note"
domain: "topic"
description: "A sourced note."
when:
  - "checking a block"
trust_tier: "verified"
version: "1.0.0"
source_attribution:
  - uri: "{URI}"
    sha256: "{digest}"
---

# Note

## Purpose

Record sourced facts.

## When to Use / When NOT

Use it when a fact is in the file.

## Core Knowledge Content

{core}## Failure Modes

1. An uncited block must fail.
"""


def _write(root, core):
    digest = _sha(SOURCE)
    source = root / URI
    source.parent.mkdir(parents=True)
    source.write_bytes(SOURCE)
    text = _document(digest, core)
    markdown = root / REL
    markdown.parent.mkdir(parents=True)
    markdown.write_text(text, encoding="utf-8")
    return text


def _claims_for(core):
    """Run verify --claims on a one-note root whose Core section is `core`."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root, core)
        return _run(["knowledge-builder", "verify", "--claims", str(root), "--legacy"])


def _line_of(text, needle):
    for number, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return number
    raise AssertionError(needle)


def _uncited(out):
    return [line for line in out.splitlines() if "uncited block:" in line]


class TestUncitedBlocks(unittest.TestCase):
    def _claims(self, core):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = _write(root, core)
            code, out, err = _run(["knowledge-builder", "verify", "--claims", str(root), "--legacy"])
        return text, code, out, err

    def test_cited_paragraph_passes(self):
        """Prose with an ease:source anchor on the same line is cited."""
        digest = _sha(SOURCE)
        core = f"The source says {QUOTE} {_anchor(digest)}\n"
        _text, code, out, err = self._claims(core)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(_uncited(out), [])
        self.assertIn("exempt blocks: 0", out)
        self.assertNotIn("no claim was checked", out)

    def test_anchor_on_the_next_line_passes(self):
        """An anchor on the following line cites the paragraph above it."""
        digest = _sha(SOURCE)
        core = f"The source says {QUOTE}\n{_anchor(digest)}\n"
        _text, code, out, err = self._claims(core)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(_uncited(out), [])
        self.assertNotIn("no claim was checked", out)

    def test_uncited_paragraph_fails_with_its_line_number(self):
        """A paragraph with no anchor fails at its own line, capped at 60 chars."""
        digest = _sha(SOURCE)
        sentence = "This sentence has no source and keeps going past the sixty character limit."
        self.assertGreater(len(sentence), 60)
        core = f"The source says {QUOTE}\n{_anchor(digest)}\n\n{sentence}\n"
        text, code, out, err = self._claims(core)
        self.assertNotEqual(code, 0, out + err)
        preview = sentence[:60]
        failure = f"{REL}:{_line_of(text, sentence)}: uncited block: {preview}"
        self.assertIn(failure, out)
        self.assertNotIn(preview + sentence[60], out)
        self.assertEqual(len(_uncited(out)), 1)
        self.assertNotIn("no claim was checked", out)

    def test_uncited_bullet_fails_when_siblings_are_cited(self):
        """Each list item is its own block. A cited sibling does not cover the next item."""
        digest = _sha(SOURCE)
        cited = f"- The source says {QUOTE}"
        uncited = "- beta was never sourced."
        core = f"{cited}\n{_anchor(digest)}\n{uncited}\n"
        text, code, out, err = self._claims(core)
        self.assertNotEqual(code, 0, out + err)
        self.assertIn(f"{REL}:{_line_of(text, uncited)}: uncited block: {uncited}", out)
        self.assertNotIn(f"uncited block: {cited}", out)
        self.assertEqual(len(_uncited(out)), 1)

    def test_table_without_anchor_fails(self):
        """A whole markdown table is one block and fails when nothing cites it."""
        digest = _sha(SOURCE)
        header = "| name | value |"
        core = (
            f"The source says {QUOTE}\n{_anchor(digest)}\n\n"
            f"{header}\n| --- | --- |\n| beta | 2 |\n"
        )
        text, code, out, err = self._claims(core)
        self.assertNotEqual(code, 0, out + err)
        self.assertIn(f"{REL}:{_line_of(text, header)}: uncited block: {header}", out)
        self.assertEqual(len(_uncited(out)), 1)

    def test_table_followed_by_an_anchor_passes(self):
        """An anchor on the line after a table cites that table."""
        digest = _sha(SOURCE)
        core = f"| name | value |\n| --- | --- |\n| alpha | 1 |\n{_anchor(digest)}\n"
        _text, code, out, err = self._claims(core)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(_uncited(out), [])
        self.assertNotIn("no claim was checked", out)

    def test_labelled_derived_line_passes(self):
        """Labels that name a non-external fact are exempt, including after a list marker."""
        digest = _sha(SOURCE)
        cited = f"The source says {QUOTE}\n{_anchor(digest)}\n"
        labels = ("Derived:", "Decision:", "Observed:")
        for label in labels:
            with self.subTest(label=label):
                core = f"{label} this is not an external fact.\n\n{cited}"
                _text, code, out, err = self._claims(core)
                self.assertEqual(code, 0, out + err)
                self.assertEqual(_uncited(out), [])
                self.assertIn("exempt blocks: 1", out)
        with self.subTest(label="list marker"):
            core = f"- Derived: this is not an external fact.\n\n{cited}"
            _text, code, out, err = self._claims(core)
            self.assertEqual(code, 0, out + err)
            self.assertEqual(_uncited(out), [])
            self.assertIn("exempt blocks: 1", out)

    def test_label_in_the_middle_of_a_sentence_is_not_exempt(self):
        """Derived: after other words is an ordinary uncited block."""
        digest = _sha(SOURCE)
        sentence = "The note mentions Derived: mid-sentence."
        core = f"The source says {QUOTE}\n{_anchor(digest)}\n\n{sentence}\n"
        text, code, out, err = self._claims(core)
        self.assertNotEqual(code, 0, out + err)
        self.assertIn(f"{REL}:{_line_of(text, sentence)}: uncited block: {sentence}", out)
        self.assertIn("exempt blocks: 0", out)
        self.assertEqual(len(_uncited(out)), 1)

    def test_multiline_anchor_cites_only_the_block_it_follows(self):
        """A multi-line anchor ends the previous block. Text after --> is a new block."""
        digest = _sha(SOURCE)
        previous = f"The source says {QUOTE}"
        following = "P2 has no source of its own."
        core = (
            f"{previous}\n\n"
            f'<!-- ease:source uri={URI} sha256={digest} quote="{QUOTE}"\n'
            f"-->{following}\n"
        )
        text, code, out, err = self._claims(core)
        self.assertNotEqual(code, 0, out + err)
        self.assertEqual(
            _uncited(out),
            [f"{REL}:{_line_of(text, following)}: uncited block: {following}"],
        )
        self.assertNotIn(f"uncited block: {previous}", out)

    def test_hidden_headings_do_not_end_core(self):
        """An indented or fenced H2 is not the end of Core. Later prose is still checked."""
        digest = _sha(SOURCE)
        supported = f"The source says {QUOTE}"
        cases = {
            "indent": (
                f"{supported}\n{_anchor(digest)}\n\n    ## Hidden\n\n"
                "Unsupported escapes the indented heading.\n"
            ),
            "tilde": (
                f"~~~\n{_anchor(digest)}\n## Hidden\n~~~\n\n"
                "Unsupported escapes the tilde fence.\n"
            ),
        }
        for name, core in cases.items():
            with self.subTest(name=name):
                _text, code, out, err = self._claims(core)
                self.assertNotEqual(code, 0, out + err)
                self.assertTrue(
                    any("Unsupported escapes" in line for line in _uncited(out)),
                    out + err,
                )
                self.assertNotIn(f"uncited block: {supported}", out)

    def test_comment_inside_a_fence_stays_inside_the_fence(self):
        """A fence is literal. An unclosed <!-- inside it must not hide later prose or labels."""
        digest = _sha(SOURCE)
        later = "Unsupported stays visible after the fence."
        swallowed = f"```html\n<!--\n```\n{_anchor(digest)}\n\n{later}\n"
        text, code, out, err = self._claims(swallowed)
        self.assertNotEqual(code, 0, out + err)
        self.assertEqual(
            _uncited(out),
            [f"{REL}:{_line_of(text, later)}: uncited block: {later}"],
        )

        cited = f"The source says {QUOTE}\n{_anchor(digest)}\n"
        decoy = f"{cited}\n```\n<!-- literal code -->\nDerived: decoy\n```\n"
        text, code, out, err = self._claims(decoy)
        preview = "<!-- literal code --> Derived: decoy"
        self.assertNotEqual(code, 0, out + err)
        self.assertIn(f"{REL}:{_line_of(text, '```')}: uncited block: {preview}", out)
        self.assertIn("exempt blocks: 0", out)

    def test_anchor_nested_in_a_comment_does_not_cite(self):
        """An ease:source marker inside another comment is comment text, not a citation."""
        digest = _sha(SOURCE)
        sentence = "Unsupported stands alone."
        core = f"{sentence}\n<!-- outer\n{_anchor(digest)}\n"
        text, code, out, err = self._claims(core)
        self.assertNotEqual(code, 0, out + err)
        self.assertEqual(
            _uncited(out),
            [f"{REL}:{_line_of(text, sentence)}: uncited block: {sentence}"],
        )

    def test_table_stops_before_a_list_item(self):
        """A list item is not a table row, even when the item contains a pipe."""
        digest = _sha(SOURCE)
        item = "- Unsupported | claim"
        core = f"| a | b |\n| --- | --- |\n| 1 | 2 | {_anchor(digest)}\n{item}\n"
        text, code, out, err = self._claims(core)
        self.assertNotEqual(code, 0, out + err)
        self.assertEqual(
            _uncited(out),
            [f"{REL}:{_line_of(text, item)}: uncited block: {item}"],
        )

    def test_blockquoted_list_items_are_separate_blocks(self):
        """Each blockquoted list item is its own block. One trailing anchor cites the last."""
        digest = _sha(SOURCE)
        first = "> - Unsupported A"
        second = "> - Unsupported B"
        core = f"{first}\n{second}\n{_anchor(digest)}\n"
        text, code, out, err = self._claims(core)
        self.assertNotEqual(code, 0, out + err)
        self.assertEqual(
            _uncited(out),
            [f"{REL}:{_line_of(text, first)}: uncited block: {first}"],
        )


if __name__ == "__main__":
    unittest.main()
