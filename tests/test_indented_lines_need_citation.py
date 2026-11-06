"""Indented lines in Core Knowledge Content need a citation, like a fence.

Four spaces or a tab open an indented code run. Consecutive indented lines,
including a blank line that is followed by more indented code, are one block.
The block is cited by an anchor under it, or exempt when a Derived, Observed,
or Decision label sits on the line directly above. A blank between the label
and the run breaks the exemption.
"""

import unittest

from tests.test_uncited_blocks import QUOTE, SOURCE, _anchor, _claims_for, _sha, _uncited

DOSE = "The dose is 10 mg/kg for every patient."
REPEAT = "Repeat the dose tomorrow."
INDENTED = f"    {DOSE}\n"
TABBED = f"\t{DOSE}\n"
CITED = f"The source says {QUOTE} {_anchor(_sha(SOURCE))}\n"


class TestIndentedLinesNeedCitation(unittest.TestCase):
    def test_four_space_line_is_an_uncited_block(self):
        code, out, err = _claims_for(f"{CITED}\n{INDENTED}")
        self.assertNotEqual(code, 0, out + err)
        self.assertEqual(len(_uncited(out)), 1, out)
        self.assertIn(DOSE, _uncited(out)[0])

    def test_tab_indented_line_is_an_uncited_block(self):
        code, out, err = _claims_for(f"{CITED}\n{TABBED}")
        self.assertNotEqual(code, 0, out + err)
        self.assertEqual(len(_uncited(out)), 1, out)
        self.assertIn(DOSE, _uncited(out)[0])

    def test_consecutive_indented_lines_are_one_block(self):
        run = f"    {DOSE}\n    {REPEAT}\n"
        code, out, err = _claims_for(f"{CITED}\n{run}")
        self.assertNotEqual(code, 0, out + err)
        self.assertEqual(len(_uncited(out)), 1, out)
        self.assertIn(DOSE, _uncited(out)[0])

    def test_blank_inside_an_indented_run_stays_one_block(self):
        run = f"    {DOSE}\n\n    {REPEAT}\n"
        code, out, err = _claims_for(f"{CITED}\n{run}")
        self.assertNotEqual(code, 0, out + err)
        self.assertEqual(len(_uncited(out)), 1, out)

    def test_anchor_under_the_indented_run_cites_it(self):
        core = f"{INDENTED}{_anchor(_sha(SOURCE))}\n"
        code, out, err = _claims_for(core)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(_uncited(out), [])

    def test_label_directly_above_exempts_the_indented_run(self):
        for label in ("Derived:", "Observed:", "Decision:", "- Derived:"):
            with self.subTest(label=label):
                code, out, err = _claims_for(f"{CITED}\n{label} the dose is ours.\n{INDENTED}")
                self.assertEqual(code, 0, out + err)
                self.assertEqual(_uncited(out), [])
                self.assertIn("exempt blocks: 2", out)

    def test_blank_between_label_and_indented_run_breaks_the_exemption(self):
        code, out, err = _claims_for(f"{CITED}\nDerived: ours.\n\n{INDENTED}")
        self.assertNotEqual(code, 0, out + err)
        self.assertEqual(len(_uncited(out)), 1, out)
        self.assertIn(DOSE, _uncited(out)[0])

    def test_prose_after_a_cited_indented_run_is_its_own_block(self):
        later = "An unsourced sentence follows the dose."
        core = f"{INDENTED}{_anchor(_sha(SOURCE))}\n\n{later}\n"
        code, out, err = _claims_for(core)
        self.assertNotEqual(code, 0, out + err)
        self.assertEqual(len(_uncited(out)), 1, out)
        self.assertIn(later, _uncited(out)[0])


if __name__ == "__main__":
    unittest.main()
