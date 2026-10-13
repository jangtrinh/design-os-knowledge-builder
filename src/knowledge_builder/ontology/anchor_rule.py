"""Rule anchors-match-cited-claims: set equality between a document's claim anchors and its `cites` links."""

import re

from knowledge_builder.ontology.claim_anchors import claim_anchors, unclosed_count
from knowledge_builder.ontology.objects import format_error

RULE = "anchors-match-cited-claims"
SOURCE_ANCHOR = re.compile(r"<!--\s*ease:source\b")


def anchor_rule_failures(ontology, graph):
    failures = []
    for obj in graph.all:
        if obj.data and obj.object_type in ontology.object_types and RULE in ontology.rules_of(obj.object_type):
            failures.extend(_one(obj))
    return failures


def _one(obj):
    failures = []
    if SOURCE_ANCHOR.search(obj.text):
        failures.append(format_error(obj.rel, "ease:source anchors are not allowed here: cite a claim with <!-- ease:claim id=... -->", "/body"))
    anchors = claim_anchors(obj.text)
    ids = set()
    if unclosed_count(obj.text) or any(a is None or set(a) != {"id"} or not a["id"] for a in anchors):
        failures.append(format_error(obj.rel, "malformed ease:claim anchor: the only attribute is id=<claim-id>", "/body"))
    ids = {a["id"] for a in anchors if a is not None and set(a) == {"id"} and a["id"]}
    cited = {target for kind, target in obj.links_out() if kind == "cites"}
    for ident in sorted(ids - cited):
        failures.append(format_error(obj.rel, f"ease:claim id={ident} is not in this document's cites links", "/body"))
    for ident in sorted(cited - ids):
        failures.append(format_error(obj.rel, f"cites '{ident}' but no ease:claim anchor uses it", "/link_types"))
    return failures
