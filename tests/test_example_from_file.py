"""Example packs freeze fixture pages through ingest --freeze --from-file."""

import json
import tempfile
import unittest
from pathlib import Path

from tests.skill_support import EXAMPLES, run_script

FIXED_FETCHED = "2026-10-13T00:00:00+00:00"


class ExampleFromFileTests(unittest.TestCase):
    def test_document_example_logs_from_file_captures(self):
        spec = next(path for path in EXAMPLES if path.name == "tiny-document-pack.json")
        run_id = json.loads(spec.read_text(encoding="utf-8"))["run"]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "pack"
            code, lines, err = run_script("build.py", "--spec", spec, "--output-dir", out)
            self.assertEqual(code, 0, err)
            log = out / "_evidence" / run_id / "captures.jsonl"
            self.assertTrue(log.is_file(), log)
            rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertGreaterEqual(len(rows), 1)
            self.assertTrue(all(row["origin"] == "from-file" for row in rows))
            sample = (out / rows[0]["path"]).read_text(encoding="utf-8")
            self.assertNotIn(FIXED_FETCHED, sample)
            self.assertTrue(sample.startswith("Source-URL: "))
