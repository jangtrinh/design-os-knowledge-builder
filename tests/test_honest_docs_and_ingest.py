"""P0.4 docs match the CLI. P0.5 ingest does not invent a source.

The skill must not send an agent at `research "<topic>" --github`.
A failed pdftotext run must raise, and must not pair the file digest
with a stand-in sentence.
"""

import hashlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from knowledge_builder.processors.image import process_image
from knowledge_builder.processors.pdf import process_pdf
from knowledge_builder.processors.video import process_video


ROOT = Path(__file__).resolve().parents[1]
EXTERNAL_ROOT = "<knowledge-root>/<domain>/<topic>"


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


class TestDocsTellTheTruth(unittest.TestCase):
    def test_skill_omits_research_github_command(self):
        """The missing research command is not advertised."""
        text = (ROOT / "skills" / "es-knowledge-forge" / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn('research "<topic>" --github', text)
        self.assertNotIn("--github", text)
        for name in ("ingest", "verify", "gate", "lint", "index"):
            self.assertIn(name, text)
        self.assertIn(EXTERNAL_ROOT, text)

    def test_readme_drops_unimplemented_claims(self):
        """Whisper, VLM, Mermaid conversion, write_atomic, and 11 scenarios are not claims."""
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        for phrase in (
            "Whisper",
            "write_atomic",
            "VLM",
            "Mermaid.js",
            "11 stopping gate scenarios",
        ):
            self.assertNotIn(phrase, text)
        self.assertIn("This repository stores no topic files.", text)
        self.assertIn(EXTERNAL_ROOT, text)

    def test_contract_doc_uses_list_source_attribution(self):
        """The contract example matches the list verify already accepts."""
        text = (ROOT / "docs" / "master-contract-ukmc.md").read_text(encoding="utf-8")
        self.assertIn("source_attribution:", text)
        self.assertIn("\n  - uri:", text)
        self.assertNotIn("\nsource:\n", text)
        page = (ROOT / "docs" / "master-contract-ukmc.html").read_text(encoding="utf-8")
        self.assertIn("source_attribution:", page)
        self.assertNotIn("source:\n", page)
        site = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        for phrase in ("Whisper", "write_atomic", "VLM", "Mermaid.js"):
            self.assertNotIn(phrase, site)


class TestIngestDoesNotInventASource(unittest.TestCase):
    def test_process_pdf_raises_when_subprocess_fails(self):
        """A failed extractor raises. The file digest is not paired with invented text."""
        payload = b"%PDF-1.4 not extracted text"
        digest = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "paper.pdf"
            pdf.write_bytes(payload)
            with patch(
                "knowledge_builder.processors.pdf.subprocess.run",
                side_effect=OSError("pdftotext missing"),
            ):
                with self.assertRaises(RuntimeError) as caught:
                    process_pdf(pdf)
            message = str(caught.exception)
            self.assertIn("pdftotext", message)
            self.assertNotIn("Extracted raw text from", message)
            self.assertNotIn(digest, message)

    def test_process_pdf_returns_caller_path_and_tool_text(self):
        """Successful text keeps the caller path. It is not file:// plus resolve()."""
        payload = b"%PDF-1.4 bytes"
        digest = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "paper.pdf"
            pdf.write_bytes(payload)
            link = Path(tmp) / "linked.pdf"
            link.symlink_to(pdf)
            completed = subprocess.CompletedProcess(
                args=["pdftotext"], returncode=0, stdout="Real page\n"
            )
            with patch(
                "knowledge_builder.processors.pdf.subprocess.run",
                return_value=completed,
            ):
                result = process_pdf(link)
            self.assertEqual(result["sha256"], digest)
            self.assertIn("Real page", result["raw_text"])
            self.assertNotIn("Extracted raw text from", result["markdown"])
            self.assertEqual(result["uri"], str(link))
            self.assertFalse(str(result["uri"]).startswith("file://"))
            self.assertNotEqual(result["uri"], f"file://{link.resolve()}")

    def test_process_image_returns_hash_uri_and_null_scaffold(self):
        """An image contributes its digest and the caller path. No invented diagram."""
        payload = b"\x89PNG-fake"
        digest = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "diagram.png"
            image.write_bytes(payload)
            link = Path(tmp) / "linked.png"
            link.symlink_to(image)
            result = process_image(link)
            self.assertEqual(result["sha256"], digest)
            self.assertEqual(result["uri"], str(link))
            self.assertIsNone(result["mermaid_scaffold"])
            self.assertFalse(str(result["uri"]).startswith("file://"))
            self.assertNotIn("Start Node", str(result["mermaid_scaffold"]))

    def test_process_video_requires_explicit_out_and_ffmpeg(self):
        """No --out means no sibling extract directory. A missing ffmpeg raises."""
        payload = b"not-a-video"
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "talk.mp4"
            video.write_bytes(payload)
            with self.assertRaises(RuntimeError):
                process_video(video)
            self.assertFalse((Path(tmp) / "extracted_talk").exists())

            out = Path(tmp) / "extracts"
            with patch(
                "knowledge_builder.processors.video.subprocess.run",
                side_effect=FileNotFoundError(2, "No such file or directory"),
            ):
                with self.assertRaises(RuntimeError) as caught:
                    process_video(video, output_dir=out)
            self.assertIn("ffmpeg", str(caught.exception))
            self.assertFalse((Path(tmp) / "extracted_talk").exists())

    def test_ingest_video_writes_only_under_out(self):
        """The CLI passes --out through and does not invent a sibling directory."""
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "talk.mp4"
            video.write_bytes(b"not-a-video")
            code, out, err = _run(["knowledge-builder", "ingest", str(video)])
            self.assertNotEqual(code, 0, out + err)
            self.assertFalse((Path(tmp) / "extracted_talk").exists())

            dest = Path(tmp) / "extracts"
            completed = subprocess.CompletedProcess(args=["ffmpeg"], returncode=0, stdout="")
            with patch(
                "knowledge_builder.processors.video.subprocess.run",
                return_value=completed,
            ):
                code, out, err = _run(
                    ["knowledge-builder", "ingest", str(video), "--out", str(dest)]
                )
            self.assertEqual(code, 0, out + err)
            self.assertFalse((Path(tmp) / "extracted_talk").exists())
            self.assertTrue((dest / "frames").is_dir())
            self.assertNotIn("file://", out)
            self.assertIn(str(video), out)
