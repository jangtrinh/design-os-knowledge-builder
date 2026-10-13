"""Stopping-gate counts read from a run ledger. No integer self-report."""

import hashlib
import json
import math
import os
from pathlib import Path

from knowledge_builder.containment import ContainmentError, file_identity, read_text_nofollow, require_inside
from knowledge_builder.quote_check import file_contains_quote
from knowledge_builder.research.ledger import AtomicResearchLedger, require_relative_source_uri
from knowledge_builder.research.stopping_gate import StoppingEvaluationInput, bool_or_absent


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
    except (OSError, TypeError, ValueError, json.JSONDecodeError, AttributeError, ContainmentError) as exc:
        raise LedgerGateError(f"unreadable ledger: {exc}") from exc
    if not isinstance(state, dict):
        raise LedgerGateError("state.json must be an object")

    required = _required_ids(state)
    verified = sum(1 for claim_id in required if _claim_verified(root, run_id, atoms, claim_id))
    block_reason = state.get("block_reason")
    return StoppingEvaluationInput(
        required_claims_total=len(required),
        required_claims_verified=verified,
        independent_sources_count=_independent_sources(root, run_id, atoms),
        has_execution_proof=_has_execution_proof(root, run_id, atoms),
        has_counterevidence_searched=_has_failure_mode(root, run_id, atoms),
        unresolved_contradictions_count=_unresolved_contradictions(state, atoms, _claim_resolved(root, run_id)),
        is_target_version_matched=_version_matched(state),
        consecutive_low_delta_rounds=_nonneg_int(state.get("consecutive_low_delta_rounds"), 0),
        last_weighted_delta=_delta(state),
        remaining_budget_calls=_nonneg_int(state.get("remaining_budget_calls"), 0),
        has_viable_probe_remaining=_probe_remaining(state),
        is_blocked=state.get("is_blocked") is True,
        block_reason=block_reason if isinstance(block_reason, str) else None,
        independent_review_passed=_review_separates_duty(run_dir, state),
        minimum_independent_sources=_minimum_sources(state),
        version_not_applicable=state.get("version_applicability") == "not_applicable",
        version_reason=_version_reason(state),
    )


def _review_separates_duty(run_dir, state):
    """True only for review.json passed by a different non-empty runtime.

    A missing or empty researcher_runtime cannot prove the reviewer is someone else.
    A missing or unreadable review file is not a pass.
    """
    researcher = state.get("researcher_runtime")
    if not isinstance(researcher, str) or researcher == "":
        return False
    path = run_dir / "review.json"
    if os.path.islink(path) or not path.is_file():
        return False
    try:
        require_inside(path, run_dir)
        review = json.loads(read_text_nofollow(path))
    except (ContainmentError, OSError, UnicodeError, json.JSONDecodeError):
        return False
    if not isinstance(review, dict) or review.get("passed") is not True:
        return False
    reviewer = review.get("reviewer_runtime")
    if not isinstance(reviewer, str) or reviewer == "":
        return False
    return reviewer != researcher


def _run_dir(root, run_id):
    if not isinstance(run_id, str) or run_id in {"", ".", ".."} or "/" in run_id or "\\" in run_id:
        raise LedgerGateError(f"run id is not a single path segment: {run_id}")
    root_path = Path(root)
    evidence = root_path / "_evidence"
    run = evidence / run_id
    for candidate in (evidence, run):
        if os.path.islink(candidate):
            raise LedgerGateError(f"refusing symlinked output: {candidate}")
    try:
        if evidence.exists():
            require_inside(evidence, root_path)
        if run.exists():
            require_inside(run, root_path)
    except ContainmentError as exc:
        raise LedgerGateError(str(exc)) from exc
    return run


def _required_ids(state):
    if "required_claim_ids" not in state:
        raise LedgerGateError("required_claim_ids must be a list of non-empty strings")
    raw = state["required_claim_ids"]
    if not isinstance(raw, list) or any(not isinstance(item, str) or item == "" for item in raw):
        raise LedgerGateError("required_claim_ids must be a list of non-empty strings")
    return list(raw)


def _meta(atom):
    return atom.metadata if isinstance(atom.metadata, dict) else {}


def _supports(atom, claim_id):
    linked = _meta(atom).get("claim")
    if isinstance(linked, str) and linked:
        return linked == claim_id
    return atom.id == claim_id


def _claim_verified(root, run_id, atoms, claim_id):
    return any(_atom_verifies_claim(root, run_id, atom, claim_id) for atom in atoms)


def _atom_verifies_claim(root, run_id, atom, claim_id):
    """Hash match plus a quote that occurs in that file. No quote stays UNCHECKED."""
    if not _supports(atom, claim_id):
        return False
    real = _source_file(root, run_id, atom.source_uri, atom.source_digest)
    if real is None:
        return False
    return file_contains_quote(real, getattr(atom, "quote", None))


def _independent_sources(root, run_id, atoms):
    """Distinct inodes under this run's sources/ (aliases do not add a source).

    In a pack (ontology.yaml with a frozen-source type) it is the distinct publishers of the Source objects the
    verified atoms map to, so two pages of one publisher count once.
    """
    found, verified = set(), []
    for atom in atoms:
        real = _source_file(root, run_id, atom.source_uri, atom.source_digest)
        if real is None:
            continue
        verified.append(atom.id)
        try:
            found.add(file_identity(real))
        except OSError:
            continue
    from knowledge_builder.ontology.claim_publishers import publisher_count

    publishers = publisher_count(root, run_id, verified)
    return len(found) if publishers is None else publishers


def _has_execution_proof(root, run_id, atoms):
    for atom in atoms:
        command = _meta(atom).get("command")
        if isinstance(command, str) and command.strip() and _source_file(
            root, run_id, atom.source_uri, atom.source_digest
        ):
            return True
    return False


def _has_failure_mode(root, run_id, atoms):
    for atom in atoms:
        if atom.claim_type == "FAILURE_MODE" and _source_file(
            root, run_id, atom.source_uri, atom.source_digest
        ):
            return True
    return False


def _claim_resolved(root, run_id):
    """Contradiction atoms an ontology root has recorded as live claims with a contradicts link."""
    from knowledge_builder.ontology.claim_resolution import resolved_atoms

    return resolved_atoms(root, run_id)


def _unresolved_contradictions(state, atoms, claim_resolved=frozenset()):
    raw = state.get("resolved") or []
    listed = ({item for item in raw if isinstance(item, str)} if isinstance(raw, list) else set()) | set(claim_resolved)
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
    """Missing or non-boolean version evidence cannot certify."""
    return bool_or_absent(state, "is_target_version_matched", absent=False)


def _version_reason(state):
    reason = state.get("version_reason")
    return reason if isinstance(reason, str) else None


def _probe_remaining(state):
    """Unknown probe status must not look like 'no probe left'."""
    return bool_or_absent(state, "has_viable_probe_remaining", absent=True)


def _delta(state):
    """None is not saturated. Any other non-finite or negative value is refused."""
    if "last_weighted_delta" not in state or state.get("last_weighted_delta") is None:
        return 1.0
    value = state.get("last_weighted_delta")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LedgerGateError("last_weighted_delta must be a finite number >= 0")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise LedgerGateError("last_weighted_delta must be a finite number >= 0")
    return number


def _minimum_sources(state):
    """A missing minimum cannot fall back to 2. Only an integer >= 1 certifies."""
    if "minimum_independent_sources" not in state:
        raise LedgerGateError("minimum_independent_sources must be an integer >= 1")
    value = state.get("minimum_independent_sources")
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise LedgerGateError("minimum_independent_sources must be an integer >= 1")
    return value


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


def _source_file(root, run_id, uri, digest):
    """Real file under this run's sources/ whose bytes match digest, else None."""
    if not isinstance(digest, str) or len(digest) != 64:
        return None
    try:
        int(digest, 16)
    except ValueError:
        return None
    rel = _repo_relative(uri)
    if rel is None:
        return None
    prefix = ("_evidence", run_id, "sources")
    parts = Path(rel).parts
    if len(parts) <= len(prefix) or parts[: len(prefix)] != prefix:
        return None
    root_path = Path(root)
    sources = root_path / "_evidence" / run_id / "sources"
    candidate = root_path / rel
    if os.path.islink(sources):
        return None
    try:
        real_sources = require_inside(sources, root_path / "_evidence" / run_id)
        real = require_inside(candidate, sources)
    except ContainmentError:
        return None
    try:
        real.relative_to(real_sources)
    except ValueError:
        return None
    if not real.is_file():
        return None
    hashed = hashlib.sha256()
    with real.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hashed.update(chunk)
    if hashed.hexdigest().lower() != digest.lower():
        return None
    return real
