"""A6/M6: look renders one sheet PNG and measures L1-L4; skipped with a reason when no browser exists."""

import struct
import tempfile
import unittest
from pathlib import Path

from tests.skill_support import SKILL, BuiltExamples, browser_available, run_script


class TestLookWithoutBrowser(BuiltExamples):
    def test_missing_browser_is_exit_2_with_the_next_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, lines, err = run_script("look.py", "--root", self.packs["tiny-document-pack"], "--sheet", Path(tmp) / "s.png",
                                          "--browser", Path(tmp) / "no-such-browser")
        self.assertEqual(code, 2)
        self.assertIn("could not run", err)
        self.assertEqual(lines, [])

    def test_missing_index_is_exit_2(self):
        root = self.mutate("tiny-document-pack")
        (root / "index.json").unlink()
        code, _lines, err = run_script("look.py", "--root", root)
        self.assertEqual(code, 2)
        self.assertIn("index.json", err)


@unittest.skipUnless(browser_available(), "no Chrome/Chromium on this machine: look.py exits 2 (LOOK: NOT RUN)")
class TestLookWithBrowser(BuiltExamples):
    def test_a6_each_example_renders_a_sheet_and_passes_l1_to_l4(self):
        for name, root in self.packs.items():
            with tempfile.TemporaryDirectory() as tmp:
                sheet = Path(tmp) / f"{name}.png"
                code, lines, err = run_script("look.py", "--root", root, "--sheet", sheet)
                self.assertEqual(code, 0, (name, lines, err))
                self.assertEqual([line.split(" ")[0] for line in lines[:4]], ["L1", "L2", "L3", "L4"])
                self.assertTrue(all(" ok: " in line for line in lines[:4]), lines)
                self.assertEqual(lines[4], f"sheet: {sheet.resolve()}")
                head = sheet.read_bytes()[:24]
                self.assertEqual(head[:8], b"\x89PNG\r\n\x1a\n")
                self.assertEqual(struct.unpack(">I", head[16:20])[0], 1440)

    def test_a_failing_machine_item_exits_1(self):
        root = self.mutate("tiny-document-pack")
        # An object on disk that index.json does not list yet: L2 compares live status against the index.
        (root / "stray.md").write_text('---\nid: "stray"\ntitle: "Stray"\nobject_type: "concept"\n---\n', encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            code, lines, err = run_script("look.py", "--root", root, "--sheet", Path(tmp) / "s.png")
        self.assertEqual(code, 1, (lines, err))
        self.assertTrue(any(line.startswith("L2 FAIL") for line in lines), lines)
        self.assertTrue(all(" ok: " in line for line in lines if line[:2] in ("L1", "L4")), lines)
