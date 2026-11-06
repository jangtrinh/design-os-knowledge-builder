"""Add ontology fields and derived properties to index entries (additive; old keys untouched)."""

import copy
import hashlib
from pathlib import Path

from knowledge_builder.ontology.cited_paths import resolve_inside
from knowledge_builder.ontology.functions import DERIVED, Context
from knowledge_builder.ontology.objects import load_graph
from knowledge_builder.ontology.schema import SCHEMA_FILE, load_ontology

PLAIN_KEYS = ("object_type", "superseded_by", "domain", "trust_tier", "when", "description")
# Whole days since capture. It changes with the clock, so a stored value is not staleness.
CLOCK_FIELDS = frozenset({"evidence_age_days"})


def schema_fingerprint(root):
    """sha256 of ontology.yaml, or None in legacy mode. Stored per entry so query can detect schema drift."""
    path = Path(root) / SCHEMA_FILE
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def enrich_entries(root, entries):
    """Mutate entries in place. Raises OntologyError when ontology.yaml is broken."""
    ontology = load_ontology(root)
    graph = load_graph(root)
    ctx = Context(root, graph)
    by_rel = {obj.rel: obj for obj in graph.all}
    fingerprint = schema_fingerprint(root)
    for entry in entries:
        entry["ontology_sha256"] = fingerprint
        obj = by_rel.get(entry["path"])
        data = obj.data if obj and obj.data else {}
        for key in PLAIN_KEYS:
            entry[key] = data.get(key)
        entry["status"] = obj.status if ontology is not None and obj else data.get("status")
        entry["links_out"] = [{"link_type": t, "target_id": i} for t, i in (obj.links_out() if obj else [])]
        entry["links_in"] = [{"link_type": t, "source_id": i} for t, i in graph.links_in(entry["id"])]
        for key, function in DERIVED.items():
            entry[key] = function(ctx, entry["id"])


def compare_enriched(root, entries):
    """Recompute enrichment. Return live entries and '{path} field {key}' diffs.

    evidence_age_days on the returned entries is the value computed now. A
    difference in that field is not a diff. The third value lists citing
    entries whose frozen capture bytes differ from the recorded sha256.
    """
    live = copy.deepcopy(entries)
    enrich_entries(root, live)
    return live, _field_diffs(entries, live), _capture_diffs(root, live)


def _field_diffs(stored_entries, live_entries):
    stored = {entry["path"]: entry for entry in stored_entries}
    diffs = []
    for entry in live_entries:
        previous = stored.get(entry["path"])
        if previous is None:
            continue
        keys = (set(previous) | set(entry)) - CLOCK_FIELDS
        for key in sorted(keys):
            if previous.get(key) != entry.get(key):
                diffs.append(f"{entry['path']} field {key}")
    return diffs


def _capture_diffs(root, live_entries):
    indexed = {entry["path"] for entry in live_entries}
    diffs = []
    for obj in load_graph(root).all:
        if obj.rel in indexed and _frozen_digest_mismatch(root, obj.data):
            diffs.append(f"{obj.rel} field source_count")
    return diffs


def _frozen_digest_mismatch(root, data):
    if not isinstance(data, dict):
        return False
    for uri, digest in _recorded_digests(data):
        path = resolve_inside(root, uri)
        if path is None or not path.is_file():
            return True  # a recorded capture that is gone no longer backs the indexed values
        try:
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            return True
        if actual != digest.strip().lower():
            return True
    return False


def _recorded_digests(data):
    pairs = []
    for item in data.get("captures") or []:
        if isinstance(item, dict):
            pairs.append((item.get("evidence_uri"), item.get("sha256")))
    for item in data.get("source_attribution") or []:
        if isinstance(item, dict):
            pairs.append((item.get("uri"), item.get("sha256")))
    for uri, digest in pairs:
        if isinstance(uri, str) and isinstance(digest, str) and digest.strip():
            yield uri, digest
