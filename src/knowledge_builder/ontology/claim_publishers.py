"""Independence for the stopping gate in a pack: distinct publishers of the Sources the verified atoms map to."""

from knowledge_builder.ontology.claim_checks import CLAIM_INTERFACE
from knowledge_builder.ontology.objects import load_graph
from knowledge_builder.ontology.schema import OntologyError, load_ontology
from knowledge_builder.ontology.source_checks import SOURCE_INTERFACE


def publisher_count(root, run_id, atom_ids):
    """Distinct publishers behind `atom_ids` of the run via claim evidence -> source. None outside a pack
    (no ontology.yaml, a broken one, or no object type implementing frozen-source): the caller keeps its inode count.
    An atom no claim records has no Source and adds nothing."""
    try:
        ontology = load_ontology(root)
    except OntologyError:
        return None
    if ontology is None or not any(ontology.implements(t, SOURCE_INTERFACE) for t in ontology.object_types):
        return None
    graph = load_graph(root)
    wanted = set(atom_ids)
    publishers = set()
    for claim in graph.all:
        if not (claim.data and claim.object_type and ontology.implements(claim.object_type, CLAIM_INTERFACE)):
            continue
        for entry in claim.data.get("evidence") or []:
            if isinstance(entry, dict) and entry.get("run") == run_id and entry.get("atom") in wanted:
                source = graph.get(entry.get("source"))
                name = source.data.get("publisher") if source and source.data else None
                if isinstance(name, str) and name.strip():
                    publishers.add(name.strip().lower())
    return len(publishers)
