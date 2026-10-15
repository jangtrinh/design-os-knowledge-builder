"""JSON-lines logs under `_actions/`: actions.jsonl (applied) and rejected.jsonl (refused, one line per attempt)."""

import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from knowledge_builder.containment import ContainmentError, ensure_real_dir, open_append_nofollow, open_lock_nofollow, write_all
from knowledge_builder.ontology.action_plan import ActionError

LOG_DIR, LOG_FILE, REJECTED_FILE = "_actions", "actions.jsonl", "rejected.jsonl"


def append_log(root, record, file_name=LOG_FILE):
    """Append one line. actions.jsonl takes its own `.lock`; rejected.jsonl is written under the root lock and adds no other file."""
    try:
        directory = ensure_real_dir(root / LOG_DIR)
        lock_fd = open_lock_nofollow(directory / ".lock") if file_name == LOG_FILE else None
    except ContainmentError as exc:
        raise ActionError(f"cannot write action log: {exc}") from exc
    try:
        if lock_fd is not None:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
        fd = open_append_nofollow(directory / file_name)
        size = os.fstat(fd).st_size
        try:
            write_all(fd, (json.dumps(record, sort_keys=True, default=str) + "\n").encode("utf-8"))
        except BaseException:
            os.ftruncate(fd, size)
            raise
        finally:
            os.close(fd)
    finally:
        if lock_fd is not None:
            os.close(lock_fd)


def record_rejection(root, name, items, reason):
    """One line per refused action. Called under the root lock, after any rollback. Legacy roots (no ontology.yaml) keep no log."""
    if not (Path(root) / "ontology.yaml").is_file():
        return
    record = {
        "action": name, "params": items[0] if len(items) == 1 else items, "reason": str(reason),
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    try:
        append_log(Path(root), record, REJECTED_FILE)
    except (ActionError, OSError):
        pass  # the refusal itself is what the caller reports; a failed trace must not mask it


def rejected_count(root):
    path = Path(root) / LOG_DIR / REJECTED_FILE
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip()) if path.is_file() else 0
    except OSError:
        return 0
