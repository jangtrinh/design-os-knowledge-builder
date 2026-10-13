"""Read-only stopping-gate check for the evidence runs an object cites."""

import re

from knowledge_builder.anchors import AnchorSyntaxError, parse_attributes
from knowledge_builder.containment import ContainmentError
from knowledge_builder.ontology.cited_paths import run_of
from knowledge_builder.ontology.claim_chain import traverse
from knowledge_builder.research.ledger_gate import LedgerGateError, ledger_evaluation_input
from knowledge_builder.research.stopping_gate import TerminationState, evaluate_stopping_gate

_ANCHOR = re.compile(r"<!--\s*ease:source\b(.*?)-->", re.DOTALL)
GUARDED_TIER = "verified"


def cited_runs(root, obj, graph=None):
    """(run ids, all_resolved): runs derived from the RESOLVED path of every cited uri.

    all_resolved is False when any citation does not resolve to _evidence/<run>/sources/<file> inside the root.
    """
    uris = []
    sources = (obj.data or {}).get("source_attribution")
    for item in sources if isinstance(sources, list) else []:
        uris.append(item.get("uri") if isinstance(item, dict) else None)
    for match in _ANCHOR.finditer(obj.text):
        try:
            uris.append((parse_attributes(match.group(1)) or {}).get("uri"))
        except AnchorSyntaxError:
            continue
    chain = traverse(graph, obj) if graph is not None else None
    uris.extend(capture.get("evidence_uri") for _source, capture in (chain.captures if chain else []))
    runs = {run_of(root, uri) for uri in uris}
    return sorted(run for run in runs if run), None not in runs


def runs_stop_sufficient(root, obj, tier, graph=None):
    """True when tier is not `verified`, or every cited run's gate decision is STOP_SUFFICIENT.

    A citation outside _evidence/<run>/sources, a missing state.json, an unreadable ledger, no cited run,
    or any other decision is False.
    """
    if tier != GUARDED_TIER:
        return True
    runs, resolved = cited_runs(root, obj, graph)
    if not runs or not resolved:
        return False
    for run in runs:
        try:
            decision = evaluate_stopping_gate(ledger_evaluation_input(root, run))
        except (LedgerGateError, ContainmentError, OSError, ValueError):
            return False
        if decision.state != TerminationState.STOP_SUFFICIENT:
            return False
    return True
