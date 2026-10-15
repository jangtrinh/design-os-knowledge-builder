"""Run one typed action: criteria, staged edits, atomic write, verify, rollback, index, log."""

import importlib
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

from knowledge_builder.containment import ContainmentError, atomic_write, ensure_real_dir, require_inside
from knowledge_builder.ontology.action_backup import Backup
from knowledge_builder.ontology.action_log import LOG_DIR, LOG_FILE, append_log, record_rejection
from knowledge_builder.ontology.action_lock import root_lock
from knowledge_builder.ontology.action_plan import (
    ActionError, Stage, action_spec, apply_edits, check_criteria, parse_params,
)
from knowledge_builder.ontology.create_object_params import is_default, prepare, reject_repeated
from knowledge_builder.ontology.functions import Context
from knowledge_builder.ontology.objects import load_graph
from knowledge_builder.ontology.schema import OntologyError, load_ontology

INDEX_FILE = "index.json"

__all__ = ["ActionError", "run_action", "run_batch", "rebuild_index"]


NATIVE = {"promote-claim": "knowledge_builder.ontology.claim_promote"}


def run_action(root, name, raw_params, verify=None):
    """Return the log record. Raises ActionError and leaves every file byte-identical on any failure."""
    return run_batch(root, name, [raw_params], verify)[0]


def run_batch(root, name, items, verify=None):
    """One root lock, one verify, one index rebuild, one log record per item. All items apply or none does."""
    root = Path(root).resolve()
    with root_lock(root):
        try:
            stage, steps = _plan(root, name, items)
            return _apply(root, name, stage, steps, verify or _structural_verify)
        except ActionError as exc:
            record_rejection(root, name, items, exc)
            raise


def _plan(root, name, items):
    """(stage, [(params, stage texts after that item)])."""
    try:
        ontology = load_ontology(root)
    except OntologyError as exc:
        raise ActionError(str(exc)) from exc
    if ontology is None:
        raise ActionError("action needs ontology.yaml; this root is in legacy mode")
    graph = load_graph(root)
    own_params = name == "create-object" and is_default(ontology)
    if not own_params:
        reject_repeated(items)
    if name in NATIVE:
        return importlib.import_module(NATIVE[name]).plan_batch(root, ontology, graph, items)
    if own_params:
        if len(items) != 1:
            raise ActionError("action create-object does not take a batch")
        spec, params = prepare(ontology, graph, items[0])
        check_criteria(spec, params, Context(root, graph))
        stage = Stage(root, graph)
        apply_edits(spec, params, stage, ontology)
        return stage, [(params, dict(stage.files))]
    spec = action_spec(ontology, name)
    if len(items) > 1 and any("create-object" in edit for edit in spec.get("edits") or []):
        raise ActionError(f"action {name} creates objects and does not take a batch")
    stage, steps, ctx = Stage(root, graph), [], Context(root, graph)
    for number, raw in enumerate(items, start=1):
        try:
            params = parse_params(spec, graph, raw)
            check_criteria(spec, params, ctx)
            apply_edits(spec, params, stage, ontology)
        except ActionError as exc:
            raise ActionError(f"item {number}: {exc}" if len(items) > 1 else str(exc)) from exc
        steps.append((params, dict(stage.files)))
    return stage, steps


def _apply(root, name, stage, steps, verify):
    originals = {rel: _read(root / rel) for rel in [*stage.files, INDEX_FILE]}
    changed = {rel: text for rel, text in stage.files.items() if originals[rel] != text.encode("utf-8")}
    if not changed:
        raise ActionError("action produced no change")
    baseline = Counter(verify(root))
    backup = Backup(root)
    try:
        for rel in [*changed, INDEX_FILE]:
            backup.save(rel)
        for rel, text in changed.items():
            _write(root, rel, text.encode("utf-8"))
        introduced = list((Counter(verify(root)) - baseline).elements())
        if introduced:
            raise ActionError("verify failed after edits:\n  " + "\n  ".join(introduced))
        rebuild_index(root)
        records = _records(name, steps, originals)
        for record in records:
            append_log(root, record)
    except BaseException:
        backup.restore()
        raise
    backup.discard()
    return records


def _records(name, steps, originals):
    """One log record per step; before/after shas chain from the on-disk bytes through each step's staged texts."""
    digest = lambda data: None if data is None else sha256(data).hexdigest()
    seen = {rel: data for rel, data in originals.items()}
    records = []
    for params, texts in steps:
        files = sorted(rel for rel, text in texts.items() if seen.get(rel) != text.encode("utf-8"))
        before = {rel: digest(seen.get(rel)) for rel in files}
        for rel in files:
            seen[rel] = texts[rel].encode("utf-8")
        records.append({
            "action": name, "params": params, "files": files, "before_sha": before,
            "after_sha": {rel: digest(seen[rel]) for rel in files},
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
    return records


def _structural_verify(root):
    from knowledge_builder.verify import verify_root

    return verify_root(root)[2]


def _read(path):
    return path.read_bytes() if path.is_file() else None


def _write(root, rel, data):
    path = Path(rel)
    if path.is_absolute() or ".." in path.parts:
        raise ActionError(f"refusing to write outside the root: {rel}")
    try:
        if not (root / path.parent).exists():
            ensure_real_dir(root / path.parent)
        require_inside(root / path.parent, root)
    except ContainmentError as exc:
        raise ActionError(f"refusing to write {rel}: {exc}") from exc
    atomic_write(root / path.parent, path.name, data)


def rebuild_index(root):
    from knowledge_builder.index import cmd_index

    try:
        cmd_index(SimpleNamespace(root=str(root), exclude=None))
    except SystemExit as exc:
        raise ActionError(f"index rebuild failed (exit {exc.code})") from exc
