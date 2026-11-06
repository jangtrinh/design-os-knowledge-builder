"""Test helper: a capture log line, and a quote long enough to verify.

Product code does not pad quotes. Tests that hand-write a capture append a
matching line here, and lengthen a quote only when it already sits in the body.
"""

import json
from pathlib import Path

import knowledge_builder
from knowledge_builder.quote_rules import quote_too_short

FETCHED = "2026-10-13T05:00:00+00:00"
PAD = " recorded across the measured sample."


def fit_quote(text):
    """Append a measured-sample phrase until the quote meets the length rule."""
    if not isinstance(text, str) or not text.strip():
        return text
    fitted = text
    while quote_too_short(fitted):
        fitted = fitted.rstrip() + PAD
    return fitted


def append_capture(root, rel, digest, origin="from-file", url=None, command=None, exit_code=None, run=None):
    """Append one captures.jsonl line whose path and sha256 match a source file."""
    parts = Path(str(rel).replace("\\", "/")).parts
    run_id = run or (parts[1] if len(parts) > 1 else "r1")
    record = {
        "path": str(rel).replace("\\", "/"),
        "sha256": digest,
        "origin": origin,
        "url": url,
        "command": command,
        "exit_code": exit_code,
        "captured_at": FETCHED,
        "tool_version": knowledge_builder.__version__,
    }
    path = Path(root) / "_evidence" / run_id / "captures.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")
