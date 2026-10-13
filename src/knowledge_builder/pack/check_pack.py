"""pack check: verify --claims, coverage, index freshness, gate. Exit 0 only when verify passes."""

from knowledge_builder.ontology.query import QueryError, load_fresh_index
from knowledge_builder.pack.status_report import build_status, load_pack
from knowledge_builder.verify import verify_root


def check_pack(root, run=None):
    """(exit code, lines). The gate decision is printed and never forced."""
    root, _ontology, _graph = load_pack(root)
    files, anchors, failures, _derived = verify_root(root, claims=True)
    status = build_status(root, run)
    lines = [f"files: {files}", f"anchors: {anchors}", f"failures: {len(failures)}", *failures]
    lines.append(
        f"coverage: claims {status['claims']['count']}, uncited claims {status['uncited_claims']}, "
        f"unpromoted atoms {'n/a' if status['unpromoted_atoms'] is None else status['unpromoted_atoms']}, "
        f"documents without claims {status['documents_without_claims']}, derived blocks {status['derived_blocks']}"
    )
    for item in status["deprecated_claims_cited"]:
        lines.append(f"deprecated claim {item['claim']} (use {item['superseded_by']}) is still cited by {', '.join(item['documents'])}: re-link or re-word")
    lines.append(f"index: {_index_state(root)}")
    gate = status["gate"]
    lines.append(f"gate: {gate['decision'] or 'n/a'} - {gate['reason']}")
    return (1 if failures else 0), lines


def _index_state(root):
    try:
        load_fresh_index(root)
    except QueryError as exc:
        return f"not fresh ({exc})"
    return "fresh"
