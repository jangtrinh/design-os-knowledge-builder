"""Read-only stopping-gate check for the evidence runs an object cites."""

import re

from knowledge_builder.anchors import AnchorSyntaxError, parse_attributes
from knowledge_builder.containment import ContainmentError
from knowledge_builder.research.ledger_gate import LedgerGateError, ledger_evaluation_input
from knowledge_builder.research.stopping_gate import TerminationState, evaluate_stopping_gate

_ANCHOR = re.compile(r"<!--\s*ease:source\b(.*?)-->", re.DOTALL)
GUARDED_TIER = "verified"


def cited_runs(obj):
    """Run ids named by `_evidence/<run>/...` in source_attribution and in ease:source anchors."""
    uris = []
    sources = (obj.data or {}).get("source_attribution")
    for item in sources if isinstance(sources, list) else []:
        uris.append(item.get("uri") if isinstance(item, dict) else None)
    for match in _ANCHOR.finditer(obj.text):
        try:
            uris.append((parse_attributes(match.group(1)) or {}).get("uri"))
        except AnchorSyntaxError:
            continue
    runs = set()
    for uri in uris:
        parts = uri.strip().split("/") if isinstance(uri, str) else []
        if len(parts) >= 3 and parts[0] == "_evidence" and parts[1]:
            runs.add(parts[1])
    return sorted(runs)


def runs_stop_sufficient(root, obj, tier):
    """True when tier is not `verified`, or every cited run's gate decision is STOP_SUFFICIENT.

    A missing state.json, an unreadable ledger, no cited run, or any other decision is False.
    """
    if tier != GUARDED_TIER:
        return True
    runs = cited_runs(obj)
    if not runs:
        return False
    for run in runs:
        try:
            decision = evaluate_stopping_gate(ledger_evaluation_input(root, run))
        except (LedgerGateError, ContainmentError, OSError, ValueError):
            return False
        if decision.state != TerminationState.STOP_SUFFICIENT:
            return False
    return True
