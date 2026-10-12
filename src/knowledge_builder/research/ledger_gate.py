"""Stopping-gate counts read from a run ledger. No integer self-report."""

import hashlib
import json
from pathlib import Path

from knowledge_builder.quote_check import file_contains_quote
from knowledge_builder.research.ledger import AtomicResearchLedger, require_relative_source_uri
from knowledge_builder.research.stopping_gate import StoppingEvaluationInput


class LedgerGateError(Exception):
    """The ledger cannot be read. The gate must not certify."""


def ledger_evaluation_input(root, run_id):
    run_dir = _run_dir(root, run_id)
    if not (run_dir / "state.json").is_file():
        raise LedgerGateError(f"run is not initialized: {run_id}")
    ledger = AtomicResearchLedger(run_id, base_dir=Path(root) / "_evidence")
    try:
        state = ledger.load_state()
        atoms = ledger.load_atoms()
    except (OSError, TypeError, ValueError, json.JSONDecodeError, AttributeError) as exc:
        raise LedgerGateError(f"unreadable ledger: {exc}") from exc
    if not isinstance(state, dict):
        raise LedgerGateError("state.json must be an object")

    required = _required_ids(state)
    verified = sum(1 for claim_id in required if _claim_verified(root, atoms, claim_id))
    block_reason = state.get("block_reason")
    return StoppingEvaluationInput(
        required_claims_total=len(required),
        required_claims_verified=verified,
        independent_sources_count=_independent_sources(root, run_id, atoms),
        has_execution_proof=_has_execution_proof(root, atoms),
        has_counterevidence_searched=_has_failure_mode(root, atoms),
        unresolved_contradictions_count=_unresolved_contradictions(state, atoms),
        is_target_version_matched=_version_matched(state),
        consecutive_low_delta_rounds=_nonneg_int(state.get("consecutive_low_delta_rounds"), 0),
        last_weighted_delta=_delta(state.get("last_weighted_delta")),
        remaining_budget_calls=_nonneg_int(state.get("remaining_budget_calls"), 0),
        has_viable_probe_remaining=_flag(state, "has_viable_probe_remaining"),
        is_blocked=state.get("is_blocked") is True,
        block_reason=block_reason if isinstance(block_reason, str) else None,
        independent_review_passed=False,
    )


def _run_dir(root, run_id):
    if not isinstance(run_id, str) or run_id in {"", ".", ".."} or "/" in run_id or "\\" in run_id:
        raise LedgerGateError(f"run id is not a single path segment: {run_id}")
    return Path(root) / "_evidence" / run_id


def _required_ids(state):
    raw = state.get("required_claim_ids") or []
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str) and item]


def _meta(atom):
    return atom.metadata if isinstance(atom.metadata, dict) else {}


def _supports(atom, claim_id):
    linked = _meta(atom).get("claim")
    if isinstance(linked, str) and linked:
        return linked == claim_id
    return atom.id == claim_id


def _claim_verified(root, atoms, claim_id):
    return any(_atom_verifies_claim(root, atom, claim_id) for atom in atoms)


def _atom_verifies_claim(root, atom, claim_id):
    """Hash match plus a quote that occurs in that file. No quote stays UNCHECKED."""
    if not _supports(atom, claim_id):
        return False
    if not _source_matches(root, atom.source_uri, atom.source_digest):
        return False
    rel = _repo_relative(atom.source_uri)
    if rel is None:
        return False
    return file_contains_quote(Path(root).resolve() / rel, getattr(atom, "quote", None))


def _independent_sources(root, run_id, atoms):
    # Distinct hash-valid files under _evidence/<run>/sources/, not a URI tally.
    found = set()
    prefix = ("_evidence", run_id, "sources")
    for atom in atoms:
        rel = _repo_relative(atom.source_uri)
        if rel is None:
            continue
        parts = Path(rel).parts
        if len(parts) <= len(prefix) or parts[: len(prefix)] != prefix:
            continue
        if _source_matches(root, atom.source_uri, atom.source_digest):
            found.add(rel)
    return len(found)


def _has_execution_proof(root, atoms):
    for atom in atoms:
        command = _meta(atom).get("command")
        if isinstance(command, str) and command.strip() and _source_matches(
            root, atom.source_uri, atom.source_digest
        ):
            return True
    return False


def _has_failure_mode(root, atoms):
    for atom in atoms:
        if atom.claim_type == "FAILURE_MODE" and _source_matches(root, atom.source_uri, atom.source_digest):
            return True
    return False


def _unresolved_contradictions(state, atoms):
    raw = state.get("resolved") or []
    listed = {item for item in raw if isinstance(item, str)} if isinstance(raw, list) else set()
    count = 0
    for atom in atoms:
        if atom.claim_type != "CONTRADICTION":
            continue
        keys = {atom.id}
        claim = _meta(atom).get("claim")
        if isinstance(claim, str) and claim:
            keys.add(claim)
        if isinstance(atom.statement, str) and atom.statement:
            keys.add(atom.statement)
        if keys.isdisjoint(listed):
            count += 1
    return count


def _version_matched(state):
    # Absence is not a recorded mismatch.
    if "is_target_version_matched" in state:
        return state.get("is_target_version_matched") is True
    return state.get("version_mismatch") is not True


def _flag(state, key):
    if key not in state:
        return False
    return state.get(key) is True


def _delta(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 1.0
    return float(value)


def _nonneg_int(value, default):
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return value if value >= 0 else 0


def _repo_relative(uri):
    try:
        rel = require_relative_source_uri(uri)
    except ValueError:
        return None
    parts = [part for part in Path(rel).parts if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        return None
    return "/".join(parts)


def _source_matches(root, uri, digest):
    if not isinstance(digest, str) or len(digest) != 64:
        return False
    try:
        int(digest, 16)
    except ValueError:
        return False
    rel = _repo_relative(uri)
    if rel is None:
        return False
    root_path = Path(root).resolve()
    candidate = (root_path / rel).resolve()
    try:
        candidate.relative_to(root_path)
    except ValueError:
        return False
    if not candidate.is_file():
        return False
    hashed = hashlib.sha256()
    with candidate.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hashed.update(chunk)
    return hashed.hexdigest().lower() == digest.lower()
