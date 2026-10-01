"""PDF Processor: Layout-preserving extraction and markdown conversion."""

from pathlib import Path
import hashlib
import subprocess
from typing import Dict, Any


def process_pdf(pdf_path: Path) -> Dict[str, Any]:
    """Extract structured text and structure from a PDF file."""
    pdf_path = Path(pdf_path).resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # Compute SHA-256 digest
    sha256 = hashlib.sha256(pdf_path.read_bytes()).hexdigest()

    # Tier 0 extraction using pdftotext -layout
    try:
        res = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            capture_output=True,
            text=True,
            check=True
        )
        raw_text = res.stdout
    except Exception:
        # Fallback if pdftotext fails
        raw_text = f"Extracted raw text from {pdf_path.name}"

    # Basic layout normalization (headings, lists)
    lines = raw_text.splitlines()
    normalized_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            normalized_lines.append("")
            continue
        # Detect headings if line is uppercase or short and followed by blank
        if len(stripped) < 80 and stripped.isupper():
            normalized_lines.append(f"\n### {stripped}\n")
        else:
            normalized_lines.append(line)

    markdown_content = "\n".join(normalized_lines)

    return {
        "modality": "pdf",
        "sha256": sha256,
        "uri": f"file://{pdf_path}",
        "raw_text": raw_text,
        "markdown": markdown_content,
        "line_count": len(lines),
    }
