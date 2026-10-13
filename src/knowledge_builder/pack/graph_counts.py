"""Counts over the object graph of a pack: types, coverage, deprecated claims still cited, independence."""

import re
from collections import Counter, defaultdict

from knowledge_builder.containment import file_identity
from knowledge_builder.ontology.cited_paths import resolve_inside
from knowledge_builder.ontology.claim_chain import traverse
from knowledge_builder.ontology.claim_checks import CLAIM_INTERFACE
from knowledge_builder.ontology.scope import DOCUMENT_INTERFACE


def of_interface(ontology, graph, interface):
    return [o for o in graph.all if o.data and o.object_type and ontology.implements(o.object_type, interface)]


def object_counts(graph):
    typed = [o for o in graph.all if o.data is not None]
    by_type_status = defaultdict(Counter)
    for obj in typed:
        by_type_status[obj.object_type or "untyped"][obj.status] += 1
    return {
        "total": len(typed),
        "by_type": dict(sorted(Counter(o.object_type or "untyped" for o in typed).items())),
        "by_status": dict(sorted(Counter(o.status for o in typed).items())),
        "by_type_status": {t: dict(sorted(c.items())) for t, c in sorted(by_type_status.items())},
    }


def coverage(ontology, graph):
    claims = of_interface(ontology, graph, CLAIM_INTERFACE)
    documents = of_interface(ontology, graph, DOCUMENT_INTERFACE)
    cited = {claim.id for claim in claims if any(kind == "cites" for kind, _s in graph.links_in(claim.id))}
    return {
        "uncited_claims": len([c for c in claims if c.id not in cited]),
        "documents_without_claims": len([d for d in documents if not any(k == "cites" for k, _t in d.links_out())]),
    }


def deprecated_cited(ontology, graph):
    """Deprecated claims that a document still cites: the documents to re-link or re-word."""
    found = []
    for claim in of_interface(ontology, graph, CLAIM_INTERFACE):
        if claim.status != "deprecated":
            continue
        documents = sorted(source for kind, source in graph.links_in(claim.id) if kind == "cites")
        if documents:
            found.append({"claim": claim.id, "superseded_by": claim.data.get("superseded_by"), "documents": documents})
    return sorted(found, key=lambda item: item["claim"])


def claim_figures(root, ontology, graph):
    claims = of_interface(ontology, graph, CLAIM_INTERFACE)
    by_file = by_publisher = 0
    statements = defaultdict(list)
    for claim in claims:
        chain = traverse(graph, claim)
        files = set()
        for _source, capture in chain.captures if chain else []:
            path = resolve_inside(root, capture.get("evidence_uri"))
            if path is not None and path.is_file():
                files.add(file_identity(path))
        by_file += len(files) >= 2
        by_publisher += len(chain.publishers()) >= 2 if chain else 0
        if claim.status != "deprecated":
            statements[re.sub(r"\s+", " ", str(claim.data.get("statement", ""))).strip().lower()].append(claim.id)
    return {
        "count": len(claims),
        "with_2_sources_by_file": by_file,
        "with_2_publishers": by_publisher,
        "duplicate_statements": sorted(sorted(ids) for text, ids in statements.items() if text and len(ids) > 1),
    }
