"""Claim coverage for the stopping gate in an ontology pack."""

from knowledge_builder.ontology.claim_chain import traverse
from knowledge_builder.ontology.claim_checks import CLAIM_INTERFACE
from knowledge_builder.ontology.objects import load_graph, message_file
from knowledge_builder.ontology.schema import OntologyError, load_ontology


def verified_pack_claims(root, run_id, verified_atom_ids):
    """(active_claim_ids, verified_claim_ids) in an ontology pack, or None outside a pack.

    An active evidence-claim counts as verified for `run_id` when it has at least one
    evidence entry in `run_id` whose atom is in `verified_atom_ids`, and neither the
    claim nor its source chain fails `verify --claims`.
    """
    try:
        ontology = load_ontology(root)
    except OntologyError:
        return None
    if ontology is None or not any(ontology.implements(t, CLAIM_INTERFACE) for t in ontology.object_types):
        return None
    graph = load_graph(root)
    active = [
        c for c in graph.all
        if c.data and c.object_type and ontology.implements(c.object_type, CLAIM_INTERFACE) and c.status != "deprecated"
    ]
    if not active:
        return [], set()
    from knowledge_builder.verify import verify_root

    failing = {message_file(m) for m in verify_root(root, claims=True)[2]}
    wanted = set(verified_atom_ids)
    verified = set()
    for claim in active:
        chain = traverse(graph, claim)
        if chain is None or failing & ({claim.rel} | chain.rels):
            continue
        entries = claim.data.get("evidence") or []
        if any(isinstance(e, dict) and e.get("run") == run_id and e.get("atom") in wanted for e in entries):
            verified.add(claim.id)
    return [c.id for c in active], verified
