"""PDF Processor: layout-preserving extraction. No invented fallback text."""

from pathlib import Path
import hashlib
import subprocess
from typing import Dict, Any


def _caller_uri(path) -> str:
    if isinstance(path, str):
        return path
    return str(path)


def process_pdf(pdf_path: Path) -> Dict[str, Any]:
    """Extract text with pdftotext. A missing binary raises RuntimeError."""
    source = Path(pdf_path)
    if not source.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    sha256 = hashlib.sha256(source.read_bytes()).hexdigest()

    try:
        res = subprocess.run(
            ["pdftotext", "-layout", str(source), "-"],
            capture_output=True,
            text=True,
            check=True,
        )
    except Exception as exc:
        raise RuntimeError("pdftotext") from exc

    raw_text = res.stdout

    lines = raw_text.splitlines()
    normalized_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            normalized_lines.append("")
            continue
        if len(stripped) < 80 and stripped.isupper():
            normalized_lines.append(f"\n### {stripped}\n")
        else:
            normalized_lines.append(line)

    markdown_content = "\n".join(normalized_lines)

    return {
        "modality": "pdf",
        "sha256": sha256,
        "uri": _caller_uri(pdf_path),
        "raw_text": raw_text,
        "markdown": markdown_content,
        "line_count": len(lines),
    }
