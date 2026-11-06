"""Stopping-gate counts read from a run ledger. No integer self-report."""

import hashlib
import json
import math
import os
from pathlib import Path

from knowledge_builder.containment import ContainmentError, file_identity, require_inside
from knowledge_builder.quote_rules import quote_failure
from knowledge_builder.research.capture_log import (
    CaptureLogError,
    capture_origin,
    execution_command,
    is_attested,
    load_captures,
)
from knowledge_builder.research.ledger import AtomicResearchLedger, require_relative_source_uri
from knowledge_builder.research.stopping_gate import StoppingEvaluationInput, bool_or_absent


class LedgerGateError(Exception):
    """The ledger cannot be read. The gate must not certify."""


def ledger_evaluation_input(root, run_id, *, recheck=False):
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

    rows = _captures(root, run_id)
    unattested = set()
    required, verified = _claim_coverage(root, run_id, state, atoms, rows, unattested)
    from knowledge_builder.research.live_sources import live_source_findings, recheck_lines
    from knowledge_builder.research.review_check import assess, must_find_atoms

    findings = live_source_findings(root, run_id, rows, atoms) if recheck else None
    quotes = {atom.id: getattr(atom, "quote", None) for atom in atoms}
    review = assess(
        root,
        run_id,
        state,
        must_find_atoms(root, run_id, state, atoms, rows, unattested),
        sources=findings,
        quotes=quotes,
    )
    execution = _has_execution_proof(root, run_id, atoms, rows, unattested)
    block_reason = state.get("block_reason")
    result = StoppingEvaluationInput(
        required_claims_total=len(required),
        required_claims_verified=verified,
        independent_sources_count=_independent_sources(root, run_id, atoms, rows, unattested, review["found_paths"]),
        has_execution_proof=execution,
        has_counterevidence_searched=_has_failure_mode(root, run_id, atoms, rows, unattested),
        unresolved_contradictions_count=_unresolved_contradictions(state, atoms, _claim_resolved(root, run_id)),
        is_target_version_matched=_version_matched(state),
        consecutive_low_delta_rounds=_nonneg_int(state.get("consecutive_low_delta_rounds"), 0),
        last_weighted_delta=_delta(state),
        remaining_budget_calls=_nonneg_int(state.get("remaining_budget_calls"), 0),
        has_viable_probe_remaining=_probe_remaining(state),
        is_blocked=state.get("is_blocked") is True,
        block_reason=block_reason if isinstance(block_reason, str) else None,
        independent_review_passed=review["passed"],
        minimum_independent_sources=_minimum_sources(state),
        version_not_applicable=state.get("version_applicability") == "not_applicable",
        version_reason=_version_reason(state),
        execution_not_applicable=state.get("execution_applicability") == "not_applicable",
        execution_reason=_execution_reason(state),
        review_failure=review["failure"],
        version_na_confirmed=review["confirm_version_na"],
        execution_na_confirmed=review["confirm_execution_na"],
    )
    result.gate_notes = _gate_notes(state, unattested)
    result.recheck_lines = recheck_lines(findings or [], execution_backed=execution) if recheck else []
    return result


def _captures(root, run_id):
    try:
        return load_captures(root, run_id)
    except (CaptureLogError, ContainmentError, OSError, UnicodeError) as exc:
        raise LedgerGateError(f"unreadable capture log: {exc}") from exc


def _gate_notes(state, unattested):
    notes = []
    if unattested:
        names = sorted(unattested)
        notes.append(f"unattested sources: {len(names)}: {', '.join(names[:5])}")
    legacy = _legacy_resolved_count(state)
    if legacy:
        notes.append(f"ignored legacy resolved entries: {legacy}")
    return notes


def _legacy_resolved_count(state):
    raw = state.get("resolved") or []
    if not isinstance(raw, list):
        return 0
    return sum(1 for item in raw if isinstance(item, str))


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
    if not isinstance(raw, list) or any(not isinstance(item, str) or not item.strip() for item in raw):
        raise LedgerGateError("required_claim_ids must be a list of non-empty strings")
    return [item.strip() for item in raw]


def _meta(atom):
    return atom.metadata if isinstance(atom.metadata, dict) else {}


def _supports(atom, claim_id):
    linked = _meta(atom).get("claim")
    if isinstance(linked, str) and linked:
        return linked == claim_id
    return atom.id == claim_id


def _claim_verified(root, run_id, atoms, claim_id, rows, unattested):
    return any(_atom_verifies_claim(root, run_id, atom, claim_id, rows, unattested) for atom in atoms)


def _atom_is_verified(root, run_id, atom, rows, unattested):
    real = _attested_source(root, run_id, atom, rows, unattested)
    return real is not None and _quote_in_capture(real, getattr(atom, "quote", None))


def _claim_coverage(root, run_id, state, atoms, rows, unattested):
    required = _required_ids(state)
    verified_atom_ids = [atom.id for atom in atoms if _atom_is_verified(root, run_id, atom, rows, unattested)]
    from knowledge_builder.ontology.claim_coverage import verified_pack_claims

    pack_claims = verified_pack_claims(root, run_id, verified_atom_ids)
    if pack_claims is None:
        verified = sum(1 for claim_id in required if _claim_verified(root, run_id, atoms, claim_id, rows, unattested))
        return required, verified
    active_ids, verified_claim_ids = pack_claims
    if not required:
        required = active_ids
    active_set = set(active_ids)
    verified = sum(
        1 for claim_id in required
        if (claim_id in verified_claim_ids if (claim_id in active_set or not state["required_claim_ids"]) else _claim_verified(root, run_id, atoms, claim_id, rows, unattested))
    )
    return required, verified


def _atom_verifies_claim(root, run_id, atom, claim_id, rows, unattested):
    """Attested hash match plus a quote in the capture body. No quote stays unverified."""
    if not _supports(atom, claim_id):
        return False
    real = _attested_source(root, run_id, atom, rows, unattested)
    return real is not None and _quote_in_capture(real, getattr(atom, "quote", None))


def _attested_source(root, run_id, atom, rows, unattested):
    """Hashed source file that a capture line attests. A hash match with no line is noted."""
    real = _source_file(root, run_id, atom.source_uri, atom.source_digest)
    if real is None:
        return None
    rel = _repo_relative(atom.source_uri)
    if rel is None or not is_attested(rows, rel, atom.source_digest):
        if rel:
            unattested.add(rel)
        return None
    return real


def _quote_in_capture(real, quote):
    try:
        text = real.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False
    return quote_failure(text, quote) is None


def _counts_independent(atom, rows, found_paths):
    """Fetched captures count. A from-file capture counts only after its quotes were re-found. Executed never counts."""
    rel = _repo_relative(atom.source_uri)
    if rel is None:
        return False
    origin = capture_origin(rows, rel, atom.source_digest)
    if origin == "executed":
        return False
    if origin == "from-file":
        return rel in found_paths
    return origin == "fetched"


def _independent_sources(root, run_id, atoms, rows, unattested, found_paths=frozenset()):
    """Distinct inodes of attested sources that count toward independence.

    In a pack (ontology.yaml with a frozen-source type) it is the distinct publishers of the Source objects the
    attested atoms map to, so two pages of one publisher count once.
    """
    found, verified = set(), []
    for atom in atoms:
        real = _attested_source(root, run_id, atom, rows, unattested)
        if real is None or not _counts_independent(atom, rows, found_paths):
            continue
        verified.append(atom.id)
        try:
            found.add(file_identity(real))
        except OSError:
            continue
    from knowledge_builder.ontology.claim_publishers import publisher_count

    publishers = publisher_count(root, run_id, verified)
    return len(found) if publishers is None else publishers


def _has_execution_proof(root, run_id, atoms, rows, unattested):
    """True only for an executed capture that exited 0 and whose logged argv matches metadata.command."""
    for atom in atoms:
        real = _attested_source(root, run_id, atom, rows, unattested)
        if real is None:
            continue
        logged = execution_command(rows, _repo_relative(atom.source_uri), atom.source_digest)
        command = _meta(atom).get("command")
        if isinstance(command, str) and logged is not None and command == logged:
            return True
    return False


def _has_failure_mode(root, run_id, atoms, rows, unattested):
    for atom in atoms:
        if atom.claim_type != "FAILURE_MODE":
            continue
        real = _attested_source(root, run_id, atom, rows, unattested)
        if real is not None and _quote_in_capture(real, getattr(atom, "quote", None)):
            return True
    return False


def _claim_resolved(root, run_id):
    """Contradiction atoms an ontology root has recorded as live claims with a contradicts link."""
    from knowledge_builder.ontology.claim_resolution import resolved_atoms

    return resolved_atoms(root, run_id)


def _resolution_ids(state):
    """Atom ids named by resolutions entries that carry a non-empty reason."""
    raw = state.get("resolutions")
    found = set()
    if not isinstance(raw, list):
        return found
    for item in raw:
        if not isinstance(item, dict):
            continue
        atom_id = item.get("atom")
        reason = item.get("reason")
        if isinstance(atom_id, str) and atom_id and isinstance(reason, str) and reason.strip():
            found.add(atom_id)
    return found


def _unresolved_contradictions(state, atoms, claim_resolved=frozenset()):
    """Contradictions with no resolutions entry and no ontology resolution."""
    listed = _resolution_ids(state) | set(claim_resolved)
    count = 0
    for atom in atoms:
        if atom.claim_type != "CONTRADICTION":
            continue
        if atom.id not in listed:
            count += 1
    return count


def _version_matched(state):
    """Missing or non-boolean version evidence cannot certify."""
    return bool_or_absent(state, "is_target_version_matched", absent=False)


def _version_reason(state):
    reason = state.get("version_reason")
    return reason if isinstance(reason, str) else None


def _execution_reason(state):
    reason = state.get("execution_reason")
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
