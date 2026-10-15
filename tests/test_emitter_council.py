"""P1.5 emitter list and council gap report.

to_markdown must emit source_attribution as a list verify can hash.
run_council_audit reports gaps. It does not return council_pass.
"""

import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from knowledge_builder.contract import (
    KnowledgeMetadata,
    ModalityType,
    SourceAttribution,
    TrustTier,
    UniversalKnowledgeUnit,
)
from knowledge_builder.frontmatter import parse_frontmatter
from knowledge_builder.research.council import run_council_audit
from knowledge_builder.research.ledger import EvidenceAtom


ROOT = Path(__file__).resolve().parents[1]


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


def _unit(sources):
    meta = KnowledgeMetadata(
        id="two-source-round-trip",
        title="Two source round trip",
        domain="agent-runtimes",
        description="Emitter output verify can hash.",
        when=["two sources", "round trip"],
        trust_tier=TrustTier.VERIFIED,
    )
    return UniversalKnowledgeUnit(
        metadata=meta,
        source=sources[0],
        sources=sources,
        purpose="Show that two attributed files survive verify.",
        when_to_use=["When the unit cites more than one frozen file"],
        when_not_to_use=["When a single file is the whole claim"],
        content="Both frozen files are cited.",
        failure_modes=["A mapping under source_attribution fails verify."],
    )


class TestEmitterRoundTrip(unittest.TestCase):
    def test_to_markdown_verify_round_trips_two_sources(self):
        """verify accepts the emitter list and both repo-relative digests."""
        payloads = [b"alpha source\n", b"beta source\n"]
        uris = [
            "_evidence/run/sources/alpha.txt",
            "_evidence/run/sources/beta.txt",
        ]
        digests = [hashlib.sha256(payload).hexdigest() for payload in payloads]
        sources = [
            SourceAttribution(
                uri=uris[0],
                modality=ModalityType.MARKDOWN,
                sha256=digests[0],
                captured_at="2026-10-12",
            ),
            SourceAttribution(
                uri=uris[1],
                modality=ModalityType.MARKDOWN,
                sha256=digests[1],
                captured_at="2026-10-12",
            ),
        ]
        markdown = _unit(sources).to_markdown()
        parsed = parse_frontmatter(markdown)
        got = [(item["uri"], item["sha256"]) for item in parsed["source_attribution"]]
        self.assertEqual(got, list(zip(uris, digests)))

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for uri, payload in zip(uris, payloads):
                path = root / uri
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)
            note = root / "notes" / "two-source-round-trip.md"
            note.parent.mkdir(parents=True, exist_ok=True)
            note.write_text(markdown, encoding="utf-8")
            code, out, err = _run(["knowledge-builder", "verify", str(root), "--legacy"])
        self.assertEqual(code, 0, out + err)
        self.assertIn("failures: 0", out)


class TestCouncilGapReport(unittest.TestCase):
    def test_empty_council_is_not_a_pass(self):
        """An empty atom list with a non-GPL license is a gap report, not council_pass."""
        report = run_council_audit([], license_name="MIT")
        self.assertNotIn("council_pass", report)
        blob = json.dumps(report)
        self.assertNotIn("permissible", blob)
        details = [gap["detail"] for gap in report["gaps"]]
        self.assertIn("missing FAILURE_MODE", details)
        self.assertIn("missing BENCHMARK", details)
        self.assertNotIn("missing a command on a verified_by_code atom", details)

    def test_verified_by_code_without_command_is_a_gap(self):
        """A verified_by_code atom with no metadata.command is named. License is ignored."""
        atoms = [
            {"id": "fail-1", "claim_type": "FAILURE_MODE", "verified_by_code": False, "metadata": {}},
            {"id": "bench-1", "claim_type": "BENCHMARK", "verified_by_code": False, "metadata": {}},
            {"id": "code-1", "claim_type": "FACT", "verified_by_code": True, "metadata": {}},
        ]
        report = run_council_audit(atoms, license_name="MIT")
        self.assertNotIn("council_pass", report)
        details = [gap["detail"] for gap in report["gaps"]]
        self.assertIn("missing a command on a verified_by_code atom", details)
        self.assertNotIn("missing FAILURE_MODE", details)
        self.assertNotIn("missing BENCHMARK", details)
        self.assertTrue(any(gap.get("atom_id") == "code-1" for gap in report["gaps"]))

    def test_satisfied_atoms_omit_those_gaps(self):
        """FAILURE_MODE, BENCHMARK, and a command clear the three named gaps."""
        atoms = [
            EvidenceAtom(
                id="fail-1",
                run_id="run-1",
                claim_type="FAILURE_MODE",
                statement="A bare gate must not certify.",
                source_uri="_evidence/run-1/sources/a.txt",
                source_digest="ab" * 32,
                captured_at="2026-10-12T00:00:00Z",
                confidence="HIGH",
                verified_by_code=False,
                metadata={},
            ),
            EvidenceAtom(
                id="bench-1",
                run_id="run-1",
                claim_type="BENCHMARK",
                statement="The suite finished.",
                source_uri="_evidence/run-1/sources/b.txt",
                source_digest="cd" * 32,
                captured_at="2026-10-12T00:00:00Z",
                confidence="HIGH",
                verified_by_code=True,
                metadata={"command": "python3 -m unittest discover -s tests -t ."},
            ),
        ]
        report = run_council_audit(atoms, license_name="GPL")
        self.assertNotIn("council_pass", report)
        details = [gap["detail"] for gap in report["gaps"]]
        self.assertNotIn("missing FAILURE_MODE", details)
        self.assertNotIn("missing BENCHMARK", details)
        self.assertNotIn("missing a command on a verified_by_code atom", details)

    def test_gate_sources_do_not_consult_council_pass(self):
        """STOP_SUFFICIENT does not read a council pass bit."""
        for relative in (
            "src/knowledge_builder/research/stopping_gate.py",
            "src/knowledge_builder/research/ledger_gate.py",
            "src/knowledge_builder/cli.py",
        ):
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn("council_pass", text)


class TestPhase9DocsAndDependency(unittest.TestCase):
    def test_skill_council_is_a_gap_report(self):
        """The skill does not treat the council as a graduation gate."""
        text = (ROOT / "skills" / "es-knowledge-forge" / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("Prior to graduation", text)
        self.assertNotIn("council_pass", text)
        self.assertIn("FAILURE_MODE", text)
        self.assertIn("BENCHMARK", text)
        self.assertIn("verified_by_code", text)
        self.assertIn("gap", text.lower())

    def test_contract_doc_drops_untrusted_markers(self):
        """The contract doc matches the emitter flag. It does not invent ingest markers."""
        text = (ROOT / "docs" / "master-contract-ukmc.md").read_text(encoding="utf-8")
        self.assertNotIn("@@UNTRUSTED_INGEST_START@@", text)
        self.assertNotIn("@@UNTRUSTED_INGEST_END@@", text)
        self.assertIn("is_external_untrusted", text)

    def test_pyproject_drops_pydantic(self):
        """Runtime dependencies stay stdlib."""
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertNotIn("pydantic", text.lower())


if __name__ == "__main__":
    unittest.main()
