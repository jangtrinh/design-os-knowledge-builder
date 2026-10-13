"""Run one typed action: criteria, staged edits, atomic write, verify, rollback, index, log."""

import fcntl
import json
import os
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

from knowledge_builder.containment import (
    ContainmentError, atomic_write, ensure_real_dir, open_append_nofollow, open_lock_nofollow, write_all,
)
from knowledge_builder.ontology.action_plan import (
    ActionError, Stage, action_spec, apply_edits, check_criteria, parse_params,
)
from knowledge_builder.ontology.functions import Context
from knowledge_builder.ontology.objects import load_graph
from knowledge_builder.ontology.schema import OntologyError, load_ontology

LOG_DIR, LOG_FILE, INDEX_FILE = "_actions", "actions.jsonl", "index.json"

__all__ = ["ActionError", "run_action", "rebuild_index"]


def run_action(root, name, raw_params, verify=None):
    """Return the log record. Raises ActionError and leaves every file byte-identical on any failure."""
    root = Path(root).resolve()
    try:
        ontology = load_ontology(root)
    except OntologyError as exc:
        raise ActionError(str(exc)) from exc
    if ontology is None:
        raise ActionError("action needs ontology.yaml; this root is in legacy mode")
    spec = action_spec(ontology, name)
    graph = load_graph(root)
    params = parse_params(spec, graph, raw_params)
    check_criteria(spec, params, Context(root, graph))
    stage = Stage(root, graph)
    apply_edits(spec, params, stage, ontology)
    originals = {rel: _read(root / rel) for rel in [*stage.files, INDEX_FILE]}
    changed = {rel: text for rel, text in stage.files.items() if originals[rel] != text.encode("utf-8")}
    if not changed:
        raise ActionError("action produced no change")
    verify = verify or _structural_verify
    baseline = set(verify(root))
    try:
        for rel, text in changed.items():
            _write(root, rel, text.encode("utf-8"))
        introduced = [line for line in verify(root) if line not in baseline]
        if introduced:
            raise ActionError("verify failed after edits:\n  " + "\n  ".join(introduced))
        rebuild_index(root)
        record = _record(name, params, root, sorted(changed), originals)
        _append_log(root, record)
    except BaseException:
        _restore(root, originals)
        raise
    return record


def _structural_verify(root):
    from knowledge_builder.verify import verify_root

    return verify_root(root)[2]


def _read(path):
    return path.read_bytes() if path.is_file() else None


def _write(root, rel, data):
    path = Path(rel)
    atomic_write(root / path.parent, path.name, data)


def _restore(root, originals):
    for rel, data in originals.items():
        if data is None:
            (root / rel).unlink(missing_ok=True)
        elif _read(root / rel) != data:
            _write(root, rel, data)


def rebuild_index(root):
    from knowledge_builder.index import cmd_index

    try:
        cmd_index(SimpleNamespace(root=str(root), exclude=None))
    except SystemExit as exc:
        raise ActionError(f"index rebuild failed (exit {exc.code})") from exc


def _record(name, params, root, files, originals):
    digest = lambda data: None if data is None else sha256(data).hexdigest()
    return {
        "action": name,
        "params": params,
        "files": files,
        "before_sha": {rel: digest(originals[rel]) for rel in files},
        "after_sha": {rel: digest(_read(root / rel)) for rel in files},
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _append_log(root, record):
    try:
        directory = ensure_real_dir(root / LOG_DIR)
        lock_fd = open_lock_nofollow(directory / ".lock")
    except ContainmentError as exc:
        raise ActionError(f"cannot write action log: {exc}") from exc
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        fd = open_append_nofollow(directory / LOG_FILE)
        try:
            write_all(fd, (json.dumps(record, sort_keys=True) + "\n").encode("utf-8"))
        finally:
            os.close(fd)
    finally:
        os.close(lock_fd)
