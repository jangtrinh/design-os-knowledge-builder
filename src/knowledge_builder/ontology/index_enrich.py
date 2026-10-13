"""Add ontology fields and derived properties to index entries (additive; old keys untouched)."""

import hashlib
from pathlib import Path

from knowledge_builder.ontology.functions import DERIVED, Context
from knowledge_builder.ontology.objects import load_graph
from knowledge_builder.ontology.schema import SCHEMA_FILE, load_ontology

PLAIN_KEYS = ("object_type", "superseded_by", "domain", "trust_tier", "when", "description")


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
