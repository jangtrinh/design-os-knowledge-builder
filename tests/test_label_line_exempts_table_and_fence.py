"""B5: a Derived:/Observed:/Decision: line directly above a table or fence exempts it.

Directly above means the very next line: a blank line between them breaks it.
The label exempts only the one block under it. Paragraphs, list items, and a
label that follows the block do not gain the exemption.
"""

import unittest

from tests.test_uncited_blocks import QUOTE, SOURCE, _anchor, _claims_for, _sha, _uncited

CITED = f"The source says {QUOTE} {_anchor(_sha(SOURCE))}\n"
TABLE = "| a | b |\n| --- | --- |\n| 1 | 2 |\n"
FENCE = "```\nsome code\n```\n"


class TestLabelExemptsBlock(unittest.TestCase):
    def test_label_directly_above_table_exempts_it(self):
        for label in ("Derived:", "Observed:", "Decision:", "- Derived:", "1. Observed:"):
            with self.subTest(label=label):
                code, out, err = _claims_for(f"{CITED}\n{label} the table is ours.\n{TABLE}")
                self.assertEqual(code, 0, out + err)
                self.assertEqual(_uncited(out), [])
                self.assertIn("exempt blocks: 2", out)

    def test_label_directly_above_fence_exempts_it(self):
        for label in ("Derived:", "Observed:", "Decision:"):
            with self.subTest(label=label):
                code, out, err = _claims_for(f"{CITED}\n{label} the snippet is ours.\n{FENCE}")
                self.assertEqual(code, 0, out + err)
                self.assertEqual(_uncited(out), [])
                self.assertIn("exempt blocks: 2", out)

    def test_blank_line_between_label_and_block_breaks_the_exemption(self):
        for block in (TABLE, FENCE):
            with self.subTest(block=block):
                code, out, err = _claims_for(f"{CITED}\nDerived: ours.\n\n{block}")
                self.assertNotEqual(code, 0, out + err)
                self.assertEqual(len(_uncited(out)), 1, out)

    def test_label_below_the_block_does_not_exempt_it(self):
        code, out, err = _claims_for(f"{CITED}\n{TABLE}Derived: ours.\n")
        self.assertNotEqual(code, 0, out + err)
        self.assertEqual(len(_uncited(out)), 1, out)

    def test_label_exempts_only_the_block_directly_under_it(self):
        core = f"{CITED}\nDerived: ours.\n{TABLE}\n{TABLE}"
        code, out, err = _claims_for(core)
        self.assertNotEqual(code, 0, out + err)
        self.assertEqual(len(_uncited(out)), 1, out)

    def test_label_above_a_paragraph_does_not_chain(self):
        code, out, err = _claims_for(f"{CITED}\nDerived: ours.\nAn unsourced sentence follows.\n")
        self.assertEqual(code, 0, out + err)  # same paragraph, label first line: existing rule
        code, out, err = _claims_for(f"{CITED}\nDerived: ours.\n- an unsourced list item\n")
        self.assertNotEqual(code, 0, out + err)
        self.assertEqual(len(_uncited(out)), 1, out)

    def test_an_unlabeled_table_or_fence_still_fails(self):
        for block in (TABLE, FENCE):
            with self.subTest(block=block):
                code, out, err = _claims_for(f"{CITED}\n{block}")
                self.assertNotEqual(code, 0, out + err)
                self.assertEqual(len(_uncited(out)), 1, out)

    def test_the_line_immediately_above_must_be_the_label(self):
        """A label two lines up, with an unlabeled line between, exempts nothing."""
        for block in (TABLE, FENCE):
            with self.subTest(block=block):
                code, out, err = _claims_for(f"{CITED}\nDerived: ours.\nan unlabeled line\n{block}")
                self.assertNotEqual(code, 0, out + err)
                self.assertEqual(len(_uncited(out)), 1, out)
                self.assertIn("exempt blocks: 1", out)

    def test_mid_sentence_label_does_not_exempt(self):
        code, out, err = _claims_for(f"{CITED}\nThe note mentions Derived: here.\n{TABLE}")
        self.assertNotEqual(code, 0, out + err)
        self.assertEqual(len(_uncited(out)), 2, out)


if __name__ == "__main__":
    unittest.main()
