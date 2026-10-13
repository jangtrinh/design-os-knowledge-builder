"""Quotes of the claims that documents cite with ease:claim anchors (what `run measure --material` counts as cited)."""

from knowledge_builder.ontology.claim_anchors import well_formed_ids
from knowledge_builder.ontology.objects import load_graph
from knowledge_builder.quote_check import normalise_newlines


def cited_claim_quotes(root):
    graph = load_graph(root)
    quotes = set()
    for obj in graph.all:
        for ident in well_formed_ids(obj.text):
            claim = graph.get(ident)
            for entry in (claim.data.get("evidence") if claim and claim.data else None) or []:
                if isinstance(entry, dict) and isinstance(entry.get("quote"), str) and entry["quote"].strip():
                    quotes.add(normalise_newlines(entry["quote"]))
    return quotes
