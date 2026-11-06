"""A Source URL follows the frozen capture when that capture names one.

metadata.url may fill in a capture that has no Source-URL header. When both
are present they must be the same after stripping. A contradiction refuses
the promotion before any claim or source is written.
"""

import hashlib
import json

from knowledge_builder.ontology.actions import ActionError, run_action
from tests.pack_support import FETCHED, PackCase, add_atom, scaffold_root


HEADER = "https://frozen.example/page"
OTHER = "https://atom.example/page"


class TestSourceUrlMustMatchCapture(PackCase):
    def setUp(self):
        super().setUp()
        scaffold_root(self.root)
        self.atom = add_atom(self.root, "a1", "page", "Alpha holds in every case.", url=HEADER)

    def _files(self):
        return sorted(
            path.relative_to(self.root).as_posix()
            for path in self.root.rglob("*")
            if path.is_file() and path.name != "rejected.jsonl"
        )

    def _rewrite(self, *, header=None, drop_header=False, meta=None):
        ledger = self.root / "_evidence" / "r1" / "evidence.jsonl"
        atoms = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
        atom = atoms[0]
        body = atom["quote"]
        if drop_header:
            data = f"{body}\n".encode("utf-8")
        else:
            data = f"Source-URL: {header}\nFetched: {FETCHED}\n\n{body}\n".encode("utf-8")
        (self.root / atom["source_uri"]).write_bytes(data)
        atom["source_digest"] = hashlib.sha256(data).hexdigest()
        if meta is not None:
            if meta == "":
                atom["metadata"].pop("url", None)
            else:
                atom["metadata"]["url"] = meta
        ledger.write_text("".join(json.dumps(item) + "\n" for item in atoms), encoding="utf-8")

    def _promote(self):
        return run_action(self.root, "promote-claim", {"atom": "a1", "kind": "official"})

    def _source_url(self):
        files = list((self.root / "sources").glob("*.md"))
        self.assertEqual(len(files), 1, [path.name for path in files])
        return files[0].read_text(encoding="utf-8")

    def test_metadata_url_that_differs_from_the_header_is_refused(self):
        self._rewrite(header=HEADER, meta=OTHER)
        before = self._files()
        with self.assertRaises(ActionError) as caught:
            self._promote()
        message = str(caught.exception)
        self.assertIn(HEADER, message)
        self.assertIn(OTHER, message)
        self.assertEqual(self._files(), before)
        self.assertEqual(list((self.root / "claims").glob("*.md")), [])
        self.assertEqual(list((self.root / "sources").glob("*.md")), [])
        rejected = (self.root / "_actions" / "rejected.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(rejected), 1)
        self.assertIn(HEADER, rejected[0])
        self.assertIn(OTHER, rejected[0])
        self.assertFalse((self.root / "_actions" / "actions.jsonl").exists())

    def test_matching_urls_use_the_frozen_header(self):
        self._rewrite(header=HEADER, meta=f"  {HEADER}  ")
        self._promote()
        self.assertIn(f'url: "{HEADER}"', self._source_url())

    def test_metadata_url_is_used_when_the_capture_has_no_header(self):
        self._rewrite(drop_header=True, meta=OTHER)
        self._promote()
        self.assertIn(f'url: "{OTHER}"', self._source_url())

    def test_blank_metadata_url_leaves_the_header_in_charge(self):
        self._rewrite(header=HEADER, meta="   ")
        self._promote()
        self.assertIn(f'url: "{HEADER}"', self._source_url())


if __name__ == "__main__":
    import unittest
    unittest.main()
