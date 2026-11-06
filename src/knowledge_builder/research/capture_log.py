"""Append-only log of captures written by ingest --freeze and run exec.

A source counts only when a line names its path and sha256. A symlinked log
or a line that is not a JSON object fails closed.
"""

import hashlib
import json
import os
import shlex
from datetime import datetime, timezone
from pathlib import Path

import knowledge_builder
from knowledge_builder.containment import ContainmentError, open_append_nofollow, read_text_nofollow, write_all


class CaptureLogError(Exception):
    """captures.jsonl cannot be trusted. Callers must not certify."""


def canonical_path(path):
    """Repo-relative capture path with one slash style and no leading ./."""
    text = str(path).replace("\\", "/").strip()
    while text.startswith("./"):
        text = text[2:]
    parts = [part for part in text.split("/") if part not in ("", ".")]
    return "/".join(parts)


def make_record(path, sha256, origin, url, command, exit_code, captured_at=None):
    """One capture line. command is an argv list or None. exit_code is an int or None."""
    return {
        "path": canonical_path(path),
        "sha256": sha256,
        "origin": origin,
        "url": url,
        "command": command,
        "exit_code": exit_code,
        "captured_at": captured_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool_version": knowledge_builder.__version__,
    }


def log_path(root, run_id):
    return Path(root) / "_evidence" / run_id / "captures.jsonl"


def append_record(root, run_id, record):
    """Append one JSON line and fsync. The caller holds the ledger lock."""
    path = log_path(root, run_id)
    if os.path.islink(path):
        raise ContainmentError(f"refusing symlinked output: {path}")
    fd = open_append_nofollow(path)
    try:
        write_all(fd, (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


def load_captures(root, run_id):
    """Capture rows. A missing log is empty. A bad line or a symlink raises."""
    path = log_path(root, run_id)
    if os.path.islink(path):
        raise ContainmentError(f"refusing symlinked output: {path}")
    if not path.exists():
        return []
    rows = []
    try:
        text = read_text_nofollow(path)
    except (ContainmentError, OSError, UnicodeError):
        raise
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CaptureLogError(f"unreadable capture log: {exc}") from exc
        if not isinstance(row, dict):
            raise CaptureLogError("unreadable capture log: line is not an object")
        rows.append(row)
    return rows


def _matches(row, path, digest):
    if not isinstance(row, dict):
        return False
    logged = row.get("sha256")
    if not isinstance(logged, str) or logged.lower() != str(digest).lower():
        return False
    return canonical_path(row.get("path", "")) == canonical_path(path)


def is_attested(rows, path, digest):
    """True when some line names this path and sha256."""
    return any(_matches(row, path, digest) for row in rows)


def capture_origin(rows, path, digest):
    """Origin of this capture. Any executed line wins; otherwise the last match."""
    origin = None
    executed = False
    for row in rows:
        if not _matches(row, path, digest):
            continue
        logged = row.get("origin")
        if logged == "executed":
            executed = True
        if isinstance(logged, str):
            origin = logged
    if executed:
        return "executed"
    return origin


def execution_command(rows, path, digest):
    """shlex.join of an executed argv whose exit_code is the integer 0, else None."""
    for row in rows:
        if not _matches(row, path, digest) or row.get("origin") != "executed":
            continue
        code = row.get("exit_code")
        command = row.get("command")
        if type(code) is not int or code != 0:
            continue
        if not isinstance(command, list) or not command or any(not isinstance(part, str) for part in command):
            continue
        return shlex.join(command)
    return None


def unattested_message(path):
    """verify --claims text for a capture no log line attests."""
    return f"unattested capture {canonical_path(path)}: re-freeze with ingest --freeze or run exec"


def attestation_failure(root, rel):
    """None when rel is not a run capture, or a log line matches its bytes.

    A capture with no matching line returns the re-freeze message. A broken log
    returns an unreadable-log message so verify fails closed.
    """
    parts = canonical_path(rel).split("/")
    if len(parts) < 4 or parts[0] != "_evidence" or parts[2] != "sources":
        return None
    path = Path(root) / Path(*parts)
    if not path.is_file() or os.path.islink(path):
        return None
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows = load_captures(root, parts[1])
    except (CaptureLogError, ContainmentError, OSError, UnicodeError) as exc:
        return f"unreadable capture log: {exc}"
    if is_attested(rows, rel, digest):
        return None
    return unattested_message(rel)
