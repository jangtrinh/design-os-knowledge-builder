"""A CONTRADICTION atom counts as resolved when a live claim records it and links the claim it contradicts."""

from knowledge_builder.ontology.claim_checks import CLAIM_INTERFACE
from knowledge_builder.ontology.objects import load_graph
from knowledge_builder.ontology.schema import OntologyError, load_ontology


def resolved_atoms(root, run_id):
    """Atom ids of `run_id` resolved through claims. Empty in legacy mode or when ontology.yaml is broken."""
    try:
        ontology = load_ontology(root)
    except OntologyError:
        return set()
    if ontology is None:
        return set()
    graph = load_graph(root)
    found = set()
    for obj in graph.all:
        if not (obj.data and obj.object_type and ontology.implements(obj.object_type, CLAIM_INTERFACE)):
            continue
        if obj.data.get("claim_type") != "CONTRADICTION" or obj.status == "deprecated":
            continue
        live = [graph.get(t) for kind, t in obj.links_out() if kind == "contradicts"]
        if any(other is not None and other.status != "deprecated" for other in live):
            found.update(e["atom"] for e in obj.data.get("evidence") or [] if isinstance(e, dict) and e.get("run") == run_id)
    return found
