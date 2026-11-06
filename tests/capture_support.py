"""Test helper: a capture log line, and a quote long enough to verify.

Product code does not pad quotes. Tests that hand-write a capture append a
matching line here, and lengthen a quote only when it already sits in the body.
"""

import html
import io
import json
from pathlib import Path
from unittest.mock import patch

import knowledge_builder
from knowledge_builder.processors.web_freeze import FreezeError
from knowledge_builder.quote_rules import capture_body, quote_too_short

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


def _pages_from_log(root, run):
    """HTML whose text is each logged capture body, keyed by that capture's url."""
    from knowledge_builder.research.capture_log import load_captures

    pages = {}
    for row in load_captures(root, run):
        if row.get("origin") not in ("fetched", "from-file"):
            continue
        url = row.get("url")
        rel = row.get("path")
        if not isinstance(url, str) or not url.strip() or not isinstance(rel, str):
            continue
        path = Path(root) / rel
        if path.is_symlink() or not path.is_file():
            continue
        body = capture_body(path.read_text(encoding="utf-8"))
        pages.setdefault(url, f"<html><body><p>{html.escape(body)}</p></body></html>")
    return pages


def run_review(root, run="run-1", reviewer="reviewer-b", verdict="pass", note="",
               confirm_version_na=False, confirm_execution_na=False, pages=None):
    """Write a current review.json. Fetch is patched; a missing page is unreachable."""
    import knowledge_builder.cli as cli_mod

    root = Path(root)
    supplied = pages is not None
    pages = dict(pages or {}) if supplied else _pages_from_log(root, run)

    def fake_fetch(url):
        if url not in pages:
            raise FreezeError(f"unreachable: {url}")
        return pages[url]

    argv = [
        "knowledge-builder", "run", "review",
        "--root", str(root), "--id", run,
        "--reviewer", reviewer, "--verdict", verdict,
    ]
    if note:
        argv.extend(["--note", note])
    if confirm_version_na:
        argv.append("--confirm-version-na")
    if confirm_execution_na:
        argv.append("--confirm-execution-na")
    out, err = io.StringIO(), io.StringIO()
    with (
        patch("sys.argv", argv),
        patch("sys.stdout", out),
        patch("sys.stderr", err),
        patch("knowledge_builder.research.run_review.fetch_html", fake_fetch),
    ):
        try:
            cli_mod.main()
            code = 0
        except SystemExit as caught:
            code = caught.code if isinstance(caught.code, int) else 1
    if code != 0:
        raise AssertionError(f"run review failed ({code}): {out.getvalue()}{err.getvalue()}")
    return code, out.getvalue(), err.getvalue()
