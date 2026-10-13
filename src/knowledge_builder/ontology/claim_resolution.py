"""A CONTRADICTION atom counts as resolved for the gate only through a verified claim that states a resolution
or has a deprecated side. Recording the contradiction (claim + contradicts link) resolves nothing."""

from knowledge_builder.ontology.claim_chain import traverse
from knowledge_builder.ontology.claim_checks import CLAIM_INTERFACE
from knowledge_builder.ontology.objects import load_graph, message_file
from knowledge_builder.ontology.schema import OntologyError, load_ontology


def resolved_atoms(root, run_id):
    """Atom ids of `run_id` resolved through claims. Empty in legacy mode or when ontology.yaml is broken.

    A claim counts when it is a CONTRADICTION with a contradicts link to an existing claim AND either has a
    non-blank string `resolution`, or it or the claim it contradicts is deprecated, AND the claim and its
    sources show no failure under `verify --claims` (quote vs capture, atom in the ledger, capture sha256).
    """
    try:
        ontology = load_ontology(root)
    except OntologyError:
        return set()
    if ontology is None:
        return set()
    graph = load_graph(root)
    candidates = [c for c in graph.all if _stated(ontology, graph, c)]
    if not candidates:
        return set()
    from knowledge_builder.verify import verify_root

    failing = {message_file(m) for m in verify_root(root, claims=True)[2]}
    found = set()
    for claim in candidates:
        chain = traverse(graph, claim)
        if chain is None or failing & ({claim.rel} | chain.rels):
            continue
        found.update(e["atom"] for e in claim.data.get("evidence") or [] if isinstance(e, dict) and e.get("run") == run_id)
    return found


def _stated(ontology, graph, claim):
    if not (claim.data and claim.object_type and ontology.implements(claim.object_type, CLAIM_INTERFACE)):
        return False
    if claim.data.get("claim_type") != "CONTRADICTION":
        return False
    others = [graph.get(t) for kind, t in claim.links_out() if kind == "contradicts"]
    others = [o for o in others if o is not None]
    resolution = claim.data.get("resolution")
    stated = isinstance(resolution, str) and resolution.strip() != ""
    return bool(others) and (stated or claim.status == "deprecated" or any(o.status == "deprecated" for o in others))
