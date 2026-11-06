"""Quote checks against the live page for logged captures an atom cites.

`run review` stores the result. `gate --recheck` and `pack check --recheck`
use the same result instead of the sources list in review.json. Tests patch
`fetch_html` in this module. Nothing here writes a source file.
"""

import hashlib
import os
from pathlib import Path

from knowledge_builder.containment import ContainmentError, require_inside
from knowledge_builder.processors.web_freeze import FreezeError, fetch_html, page_text
from knowledge_builder.quote_rules import quote_failure
from knowledge_builder.research.capture_log import canonical_path

OFFLINE_NOTE = "note: sources were checked by the review, not now; rerun with --recheck to fetch them"
EXECUTION_NOTE = "recheck: execution captures are not re-run"


def live_source_findings(root, run_id, rows, atoms):
    """One entry per attested fetched or from-file capture an atom cites.

    The shape matches review.json "sources". A page that cannot be fetched is
    unreachable, and every citing quote is then missing.
    """
    seen = set()
    listed = []
    prefix = f"_evidence/{run_id}/"
    for row in rows:
        if row.get("origin") not in ("fetched", "from-file"):
            continue
        path = canonical_path(row.get("path", ""))
        digest = row.get("sha256")
        if not path.startswith(prefix) or path in seen or not _matches_file(root, path, digest):
            continue
        citing = _citing(atoms, path, digest)
        if not citing:
            continue
        seen.add(path)
        url = row.get("url") if isinstance(row.get("url"), str) and row.get("url").strip() else None
        status, found, missing = _check_url(url, citing)
        listed.append(
            {
                "url": url,
                "path": path,
                "status": status,
                "quotes_found": found,
                "quotes_total": len(citing),
                "missing_atoms": missing,
            }
        )
    return listed


def recheck_lines(findings, *, execution_backed):
    """Lines printed after a live fetch. The execution line is added only when one backs proof."""
    fetched = unreachable = missing = 0
    for entry in findings:
        if not isinstance(entry, dict):
            continue
        if entry.get("status") == "ok":
            fetched += 1
        elif entry.get("status") == "unreachable":
            unreachable += 1
        names = entry.get("missing_atoms")
        if isinstance(names, list):
            missing += len(names)
    lines = [f"recheck: {fetched} sources fetched, {unreachable} unreachable, {missing} quotes missing"]
    if execution_backed:
        lines.append(EXECUTION_NOTE)
    return lines


def _matches_file(root, rel, digest):
    if not isinstance(digest, str) or len(digest) != 64:
        return False
    path = Path(root) / rel
    if os.path.islink(path) or not path.is_file():
        return False
    try:
        require_inside(path, Path(root))
        hashed = hashlib.sha256(path.read_bytes()).hexdigest()
    except (ContainmentError, OSError):
        return False
    return hashed.lower() == digest.lower()


def _citing(atoms, path, digest):
    found = []
    for atom in atoms:
        rel = canonical_path(getattr(atom, "source_uri", ""))
        logged = getattr(atom, "source_digest", "")
        if rel == path and isinstance(logged, str) and logged.lower() == digest.lower():
            found.append(atom)
    return found


def _check_url(url, citing):
    missing_ids = [atom.id for atom in citing]
    if not url:
        return "unreachable", 0, missing_ids
    try:
        text = page_text(fetch_html(url))
    except (FreezeError, OSError):
        return "unreachable", 0, missing_ids
    missing = []
    found = 0
    for atom in citing:
        if quote_failure(text, getattr(atom, "quote", None)) is None:
            found += 1
        else:
            missing.append(atom.id)
    return "ok", found, missing
