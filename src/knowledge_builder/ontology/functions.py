"""Built-in function registry. Names come from ontology.yaml; code never loads from a root."""

import time
from dataclasses import dataclass
from pathlib import Path

from knowledge_builder.ontology.objects import message_file


@dataclass
class Context:
    root: Path
    graph: object


def _status_of(ctx, ident):
    obj = ctx.graph.get(ident)
    return obj.status if obj else None


def object_exists(ctx, ident):
    return ctx.graph.get(ident) is not None


def status_is(ctx, ident, status):
    return _status_of(ctx, ident) == status


def has_link(ctx, source, link_type, target):
    obj = ctx.graph.get(source)
    return bool(obj) and (link_type, target) in obj.links_out()


def claims_verified(ctx, ident):
    """True when `verify --claims` reports nothing for that object's file."""
    from knowledge_builder.verify import verify_root

    obj = ctx.graph.get(ident)
    if obj is None:
        return False
    _files, _anchors, failures, _exempt = verify_root(ctx.root, claims=True)
    return not any(message_file(message) == obj.rel for message in failures)


def source_count(ctx, ident):
    obj = ctx.graph.get(ident)
    sources = obj.data.get("source_attribution") if obj and obj.data else None
    return len(sources) if isinstance(sources, list) else 0


def evidence_age_days(ctx, ident):
    """Age of the OLDEST cited source file (worst-case staleness); None when none resolve."""
    obj = ctx.graph.get(ident)
    sources = obj.data.get("source_attribution") if obj and obj.data else None
    oldest = None
    for item in sources if isinstance(sources, list) else []:
        uri = item.get("uri") if isinstance(item, dict) else None
        path = (ctx.root / uri) if isinstance(uri, str) and not uri.startswith("/") else None
        if path is not None and path.is_file():
            mtime = path.stat().st_mtime
            oldest = mtime if oldest is None else min(oldest, mtime)
    return None if oldest is None else max(0, int((time.time() - oldest) // 86400))


def links_in_count(ctx, ident):
    return len(ctx.graph.links_in(ident))


FUNCTIONS = {
    "object-exists": object_exists,
    "status-is": status_is,
    "has-link": has_link,
    "claims-verified": claims_verified,
    "source-count": source_count,
    "evidence-age-days": evidence_age_days,
    "links-in-count": links_in_count,
}
DERIVED = {"source_count": source_count, "evidence_age_days": evidence_age_days, "links_in_count": links_in_count}
