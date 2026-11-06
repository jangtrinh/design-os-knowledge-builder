"""Whether review.json still matches this run.

A review counts when a different runtime recorded it and its three hashes
still match the ledger, the capture log, and the claim files. A file that
only says it passed is not a review. The gate names a stale file or a quote
the re-fetch did not find.
"""

import hashlib
import json
import os
from pathlib import Path

from knowledge_builder.containment import ContainmentError, read_text_nofollow, require_inside
from knowledge_builder.research.capture_log import canonical_path
from knowledge_builder.research.review_find import must_find_atoms

__all__ = ["assess", "claims_digest", "digest_file", "load_review", "must_find_atoms"]

_HEX = frozenset("0123456789abcdef")


def digest_file(path):
    """sha256 of a regular file. A missing file hashes empty bytes. A symlink is refused."""
    path = Path(path)
    if os.path.islink(path):
        return None
    if not path.exists():
        return hashlib.sha256(b"").hexdigest()
    if not path.is_file():
        return None
    hashed = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hashed.update(chunk)
    return hashed.hexdigest()


def claims_digest(root):
    """sha256 of claim files under an ontology pack, or None when there is no ontology.yaml."""
    root = Path(root)
    ontology = root / "ontology.yaml"
    if os.path.islink(ontology) or not ontology.is_file():
        return None
    hashed = hashlib.sha256()
    claims = root / "claims"
    files = []
    if claims.is_dir() and not os.path.islink(claims):
        for path in claims.rglob("*"):
            if path.is_symlink() or not path.is_file():
                continue
            files.append((path.relative_to(claims).as_posix(), path))
    for rel, path in sorted(files):
        hashed.update(rel.encode("utf-8"))
        hashed.update(b"\0")
        hashed.update(path.read_bytes())
        hashed.update(b"\0")
    return hashed.hexdigest()


def _hex64(value):
    return isinstance(value, str) and len(value) == 64 and all(ch in _HEX for ch in value.lower())


def _recognized(review):
    if not isinstance(review, dict):
        return False
    reviewer = review.get("reviewer_runtime")
    if not isinstance(reviewer, str) or not reviewer.strip():
        return False
    if review.get("verdict") not in ("pass", "fail"):
        return False
    if not isinstance(review.get("note"), str):
        return False
    reviewed_at = review.get("reviewed_at")
    if not isinstance(reviewed_at, str) or not reviewed_at.strip():
        return False
    if not _hex64(review.get("ledger_sha256")) or not _hex64(review.get("captures_sha256")):
        return False
    if "claims_sha256" not in review:
        return False
    claims = review.get("claims_sha256")
    if claims is not None and not _hex64(claims):
        return False
    if type(review.get("confirm_version_na")) is not bool or type(review.get("confirm_execution_na")) is not bool:
        return False
    return isinstance(review.get("sources"), list)


def load_review(run_dir):
    """The review object when the file has the bound fields, else None."""
    path = Path(run_dir) / "review.json"
    if os.path.islink(path) or not path.is_file():
        return None
    try:
        require_inside(path, run_dir)
        review = json.loads(read_text_nofollow(path))
    except (ContainmentError, OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not _recognized(review):
        return None
    return review


def _separated(review, state):
    researcher = state.get("researcher_runtime") if isinstance(state, dict) else None
    reviewer = review.get("reviewer_runtime")
    if not isinstance(researcher, str) or not researcher.strip():
        return False
    if not isinstance(reviewer, str) or not reviewer.strip():
        return False
    return reviewer.strip() != researcher.strip()


def _same(recorded, current):
    if current is None or not isinstance(recorded, str):
        return False
    return recorded.lower() == current.lower()


def _stale_reason(review, root, run_id):
    run = Path(root) / "_evidence" / run_id
    if not _same(review.get("ledger_sha256"), digest_file(run / "evidence.jsonl")):
        return "review is stale: evidence.jsonl changed after review"
    if not _same(review.get("captures_sha256"), digest_file(run / "captures.jsonl")):
        return "review is stale: captures.jsonl changed after review"
    current = claims_digest(root)
    recorded = review.get("claims_sha256")
    if current is None:
        if recorded is not None:
            return "review is stale: claims changed after review"
    elif not _same(recorded, current):
        return "review is stale: claims changed after review"
    return None


def _quotes_found(entry):
    missing = entry.get("missing_atoms") if isinstance(entry, dict) else None
    return (
        isinstance(entry, dict)
        and entry.get("status") == "ok"
        and entry.get("quotes_found") == entry.get("quotes_total")
        and isinstance(missing, list)
        and not missing
    )


def _by_path(review):
    found = {}
    for entry in review.get("sources") or []:
        if isinstance(entry, dict) and isinstance(entry.get("path"), str):
            found.setdefault(canonical_path(entry["path"]), entry)
    return found


def assess(root, run_id, state, must_find):
    """passed, failure text, confirm flags, and paths whose quotes were all found.

    must_find maps an atom id to its capture path. Executed captures are omitted
    by the caller. Confirm flags and found paths need a current review. The
    pass verdict is separate from those flags.
    """
    view = {
        "passed": False,
        "failure": None,
        "confirm_version_na": False,
        "confirm_execution_na": False,
        "found_paths": frozenset(),
    }
    review = load_review(Path(root) / "_evidence" / run_id)
    if review is None or not _separated(review, state):
        return view
    stale = _stale_reason(review, root, run_id)
    if stale:
        view["failure"] = stale
        return view
    view["confirm_version_na"] = review.get("confirm_version_na") is True
    view["confirm_execution_na"] = review.get("confirm_execution_na") is True
    view["found_paths"] = frozenset(
        canonical_path(entry["path"])
        for entry in review["sources"]
        if isinstance(entry, dict) and isinstance(entry.get("path"), str) and _quotes_found(entry)
    )
    if review.get("verdict") != "pass":
        return view
    missing = []
    sources = _by_path(review)
    for atom_id, path in must_find.items():
        entry = sources.get(canonical_path(path))
        names = entry.get("missing_atoms") if isinstance(entry, dict) else None
        if not isinstance(names, list):
            names = []
        if not (isinstance(entry, dict) and entry.get("status") == "ok" and atom_id not in names):
            missing.append(atom_id)
    if missing:
        view["failure"] = "; ".join(f"quote not found on live page for {atom_id}" for atom_id in missing)
        return view
    view["passed"] = True
    return view
