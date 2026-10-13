"""Object sets: read-only filters over index.json. Refuses a stale index."""

import hashlib
import json
from pathlib import Path

from knowledge_builder.containment import ContainmentError, read_bytes_inside
from knowledge_builder.index import DEFAULT_EXCLUDE, _markdown_files
from knowledge_builder.ontology.schema import load_ontology


class QueryError(ValueError):
    """The query cannot run: stale or missing index, unknown field, bad filter."""


def load_fresh_index(root):
    root = Path(root).resolve()
    try:
        entries = json.loads((root / "index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise QueryError(f"index.json is missing or unreadable ({exc}): run index") from exc
    stale = _stale_paths(root, entries)
    if stale:
        shown = ", ".join(stale[:5]) + (f" and {len(stale) - 5} more" if len(stale) > 5 else "")
        raise QueryError(f"index.json is stale for {shown}: run index")
    return entries


def _stale_paths(root, entries):
    files, _errors = _markdown_files(root, [DEFAULT_EXCLUDE])
    on_disk = {path.relative_to(root).as_posix(): path for path in files}
    indexed = {entry["path"]: entry["sha256"] for entry in entries}
    stale = set(on_disk) ^ set(indexed)
    for rel in set(on_disk) & set(indexed):
        try:
            digest = hashlib.sha256(read_bytes_inside(on_disk[rel], root)).hexdigest()
        except (ContainmentError, OSError):
            stale.add(rel)
            continue
        if digest != indexed[rel]:
            stale.add(rel)
    return sorted(stale)


def run_query(root, *, object_type=None, status=None, linked_to=None, link_type=None,
              implements=None, where=(), fields=None):
    entries = load_fresh_index(root)
    if implements:
        ontology = load_ontology(Path(root))
        if ontology is None:
            raise QueryError("--implements needs ontology.yaml")
        types = set(ontology.implementing(implements))
        entries = [e for e in entries if e.get("object_type") in types]
    if object_type:
        entries = [e for e in entries if e.get("object_type") == object_type]
    if status:
        entries = [e for e in entries if e.get("status") == status]
    if linked_to:
        entries = [e for e in entries if _linked(e, linked_to, link_type)]
    for clause in where:
        key, sep, value = clause.partition("=")
        if not sep or not key:
            raise QueryError(f"--where needs key=value, got {clause!r}")
        entries = [e for e in entries if _matches(e.get(key), value)]
    entries.sort(key=lambda e: e["id"])
    return _project(entries, fields)


def _linked(entry, ident, link_type):
    pairs = [(l["link_type"], l["target_id"]) for l in entry.get("links_out", [])]
    pairs += [(l["link_type"], l["source_id"]) for l in entry.get("links_in", [])]
    return any(other == ident and (link_type is None or kind == link_type) for kind, other in pairs)


def _matches(actual, wanted):
    if isinstance(actual, list):
        return wanted in [str(item) for item in actual]
    return actual is not None and str(actual) == wanted


def _project(entries, fields):
    if not fields:
        return entries
    names = [name.strip() for name in fields.split(",") if name.strip()]
    known = set(entries[0]) if entries else set(names)
    for name in names:
        if name not in known:
            raise QueryError(f"unknown field {name!r}; index has {sorted(known)}")
    return [{name: entry.get(name) for name in names} for entry in entries]
