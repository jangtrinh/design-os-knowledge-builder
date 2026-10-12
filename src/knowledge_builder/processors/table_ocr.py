"""Table OCR extractor. Shells out to tesseract when it is on PATH.

The core install does not import an OCR library. A missing binary or a
non-zero exit raises RuntimeError. The text is tesseract's own output.
"""

import shutil
import subprocess


def process_table_ocr(image_path, layout="plain"):
    """Return tesseract text. `layout` is `plain` or `tsv`."""
    if layout not in ("plain", "tsv"):
        raise RuntimeError("table ocr layout must be 'plain' or 'tsv'")
    binary = shutil.which("tesseract")
    if binary is None:
        raise RuntimeError("missing optional extra 'ocr' (binary 'tesseract')")
    argv = [binary, str(image_path), "stdout"]
    if layout == "tsv":
        argv.append("tsv")
    return _run_tesseract(argv).stdout


def _run_tesseract(argv):
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        raise RuntimeError(f"table ocr extractor tesseract failed to start: {exc}") from exc
    if completed.returncode != 0:
        raise RuntimeError(f"table ocr extractor tesseract exited {completed.returncode}")
    return completed
