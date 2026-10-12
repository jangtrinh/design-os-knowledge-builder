"""P0.3 index: real sha256, evidence excluded, root outside the package.

The knowledge root is an external directory. The tool repo is not a root.
"""

import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


NOTE = """---
id: note
title: "A note"
---

# Note

Body.
"""


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


def _package_directory():
    import knowledge_builder.cli as cli_mod

    here = Path(cli_mod.__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    raise AssertionError("pyproject.toml not found above knowledge_builder")


class TestIndexKnowledgeRoot(unittest.TestCase):
    def test_excludes_evidence_and_writes_real_sha256(self):
        """note.md is indexed; _evidence/x/frozen.md is not; the digest is the file bytes."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            note = root / "note.md"
            note.write_text(NOTE, encoding="utf-8")
            frozen = root / "_evidence" / "x" / "frozen.md"
            frozen.parent.mkdir(parents=True)
            frozen.write_text("frozen source\n", encoding="utf-8")
            (root / "readme.md").write_text("# readme\n", encoding="utf-8")

            code, out, err = _run(["knowledge-builder", "index", "--root", str(root)])
            self.assertEqual(code, 0, out + err)
            self.assertNotIn("placeholder-hash", out)

            index_path = root / "index.json"
            text = index_path.read_text(encoding="utf-8")
            self.assertNotIn("placeholder-hash", text)
            self.assertNotIn("frozen.md", text)
            self.assertNotIn("_evidence", text)
            entries = json.loads(text)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["path"], "note.md")
            self.assertEqual(entries[0]["id"], "note")
            self.assertEqual(entries[0]["sha256"], hashlib.sha256(note.read_bytes()).hexdigest())

    def test_root_inside_package_exits_2(self):
        """A directory under the tree that contains this pyproject.toml is refused."""
        package = _package_directory()
        with tempfile.TemporaryDirectory(dir=package) as tmp:
            code, out, err = _run(["knowledge-builder", "index", "--root", tmp])
            self.assertEqual(code, 2, out + err)
            self.assertFalse((Path(tmp) / "index.json").exists())

    def test_id_mismatch_with_filename_is_an_error(self):
        """Frontmatter id must match the markdown filename stem."""
        body = '---\nid: other-name\ntitle: "Note"\n---\n\n# Note\n'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "note.md").write_text(body, encoding="utf-8")
            code, out, err = _run(["knowledge-builder", "index", "--root", str(root)])
            self.assertNotEqual(code, 0, out + err)
            self.assertNotEqual(code, 2, out + err)
            self.assertIn("note.md", out + err)
            self.assertFalse((root / "index.json").exists())


if __name__ == "__main__":
    unittest.main()
