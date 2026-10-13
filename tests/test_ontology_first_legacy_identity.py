"""C-A1: a root without ontology.yaml prints exactly what `main` printed before the ontology-first work.

The expected texts below were produced by running `verify` from the main checkout (c0cfe7e) on the same roots.
"""

import shutil
import unittest
from pathlib import Path

from tests.pack_support import PackCase
from tests.test_ontology_support import FIXTURE, run_cli

CLEAN = "files: 3\nanchors: 3\nfailures: 0\n"
CLEAN_CLAIMS = CLEAN + "exempt blocks: 0\n"
BROKEN = """files: 4
anchors: 3
failures: 12
alpha.md: missing heading ## Purpose
extra.md: missing title
extra.md: missing domain
extra.md: missing description
extra.md: missing when
extra.md: missing trust_tier
extra.md: missing version
extra.md: source_attribution must be a non-empty list of {uri, sha256}
extra.md: missing heading ## Purpose
extra.md: missing heading ## When to Use / When NOT
extra.md: missing heading ## Core Knowledge Content
extra.md: missing heading ## Failure Modes
"""
WARNING = "[WARN] no ontology.yaml: legacy mode, UKMC.v1 checks only\n"


class TestLegacyIdentity(PackCase):
    def legacy(self):
        shutil.copytree(FIXTURE, self.root)
        (self.root / "ontology.yaml").unlink()

    def verify_cli(self, *flags):
        return run_cli(["knowledge-builder", "verify", str(self.root), *flags])

    def test_clean_legacy_root(self):
        self.legacy()
        self.assertEqual(self.verify_cli(), (0, CLEAN, WARNING))
        self.assertEqual(self.verify_cli("--claims"), (0, CLEAN_CLAIMS, WARNING))

    def test_broken_legacy_root_keeps_every_v1_failure_and_exit_code(self):
        self.legacy()
        self.replace("alpha.md", "## Purpose", "## Intro")
        (self.root / "extra.md").write_text('---\nid: "extra"\n---\nbody\n')
        self.assertEqual(self.verify_cli(), (1, BROKEN, WARNING))

    def test_claim_and_source_folders_get_no_special_treatment_in_legacy_mode(self):
        self.legacy()
        (self.root / "claims").mkdir()
        (self.root / "claims" / "c.md").write_text('---\nid: "c"\nobject_type: "claim"\n---\nbody\n')
        code, out, _err = self.verify_cli()
        self.assertEqual(code, 1)
        self.assertIn("claims/c.md: missing title", out)  # v1 still applies to every file


if __name__ == "__main__":
    unittest.main()
