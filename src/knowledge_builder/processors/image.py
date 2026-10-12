"""Image processor: digest and caller path. No invented diagram."""

from pathlib import Path
import hashlib
from typing import Dict, Any


def _caller_uri(path) -> str:
    if isinstance(path, str):
        return path
    return str(path)


def process_image(image_path: Path) -> Dict[str, Any]:
    """Hash an image. Diagram-to-code is not implemented."""
    source = Path(image_path)
    if not source.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    sha256 = hashlib.sha256(source.read_bytes()).hexdigest()

    return {
        "modality": "image",
        "sha256": sha256,
        "uri": _caller_uri(image_path),
        "mermaid_scaffold": None,
    }
