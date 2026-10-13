"""Built-in function registry. Names come from ontology.yaml; code never loads from a root."""

import datetime
import re
from dataclasses import dataclass
from pathlib import Path

from knowledge_builder.ontology.objects import message_file
from knowledge_builder.ontology.run_gate import runs_stop_sufficient as _runs_stop_sufficient


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


_FETCHED = re.compile(r"^Fetched:\s*(\S+)", re.MULTILINE)


def _cited_moment(path):
    """When a cited source was captured: its `Fetched:` header line, else the file mtime."""
    with path.open("rb") as handle:
        head = handle.read(4096).decode("utf-8", errors="replace")
    match = _FETCHED.search(head)
    if match:
        try:
            moment = datetime.datetime.fromisoformat(match.group(1).replace("Z", "+00:00"))
            return moment if moment.tzinfo else moment.replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            pass
    return datetime.datetime.fromtimestamp(path.stat().st_mtime, datetime.timezone.utc)


def evidence_age_days(ctx, ident):
    """Whole days since the OLDEST cited source was captured; None when no cited file resolves."""
    obj = ctx.graph.get(ident)
    sources = obj.data.get("source_attribution") if obj and obj.data else None
    moments = []
    for item in sources if isinstance(sources, list) else []:
        uri = item.get("uri") if isinstance(item, dict) else None
        path = (ctx.root / uri) if isinstance(uri, str) and not uri.startswith("/") else None
        if path is not None and path.is_file():
            moments.append(_cited_moment(path))
    if not moments:
        return None
    return max(0, (datetime.datetime.now(datetime.timezone.utc) - min(moments)).days)


def runs_stop_sufficient(ctx, ident, tier):
    obj = ctx.graph.get(ident)
    return obj is not None and _runs_stop_sufficient(ctx.root, obj, tier)


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
    "runs-stop-sufficient": runs_stop_sufficient,
}
DERIVED = {"source_count": source_count, "evidence_age_days": evidence_age_days, "links_in_count": links_in_count}
