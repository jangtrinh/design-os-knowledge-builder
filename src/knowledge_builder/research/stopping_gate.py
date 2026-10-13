"""Stopping Gate & Saturation Evaluator for Auto-Research.
Formulated with Codex Native Astra: 4 distinct termination states,
hard gates, and semantic saturation tracking.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any, Optional
import hashlib
import json


class TerminationState(str, Enum):
    STOP_SUFFICIENT = "STOP_SUFFICIENT"
    DEEPEN = "DEEPEN"
    PAUSE_BUDGET = "PAUSE_BUDGET"
    ABSTAIN_BLOCKED = "ABSTAIN_BLOCKED"


@dataclass
class StoppingEvaluationInput:
    # Hard Gate criteria
    required_claims_total: int
    required_claims_verified: int
    independent_sources_count: int
    has_execution_proof: bool
    has_counterevidence_searched: bool
    unresolved_contradictions_count: int
    is_target_version_matched: bool
    
    # Saturation metrics. None means the value was not measured.
    consecutive_low_delta_rounds: Optional[int]  # Threshold: >= 3
    last_weighted_delta: Optional[float]         # Threshold: <= 0.02 (2%)
    
    # Budget & operational state
    remaining_budget_calls: int
    has_viable_probe_remaining: bool
    is_blocked: bool = False
    block_reason: Optional[str] = None
    independent_review_passed: bool = False
    minimum_independent_sources: int = 2
    # A pack with no target library declares the version gate not applicable.
    # It passes only with a non-empty reason, which the gate prints.
    version_not_applicable: bool = False
    version_reason: Optional[str] = None


@dataclass
class StoppingDecision:
    state: TerminationState
    reason: str
    hard_gates_passed: bool
    saturation_passed: bool
    certificate: Optional[Dict[str, Any]] = None
    version_note: Optional[str] = None


def _require_minimum_sources(value):
    """Reject a missing, typed-wrong, or non-positive source minimum."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("minimum_independent_sources must be an integer >= 1")
    return value


def bool_or_absent(source, name, *, absent):
    """Keep a real bool. Missing, None, and every other type take absent.

    Version match uses absent=False, so only True certifies.
    Probe status uses absent=True, so only False means no probe remains.
    """
    if isinstance(source, dict):
        value = source[name] if name in source else None
    else:
        value = getattr(source, name, None)
    if isinstance(value, bool):
        return value
    return absent


def version_not_applicable_reason(inp):
    """The stated reason when the version gate is declared not applicable, else None.

    A declaration without a non-empty string reason is not a declaration.
    """
    if getattr(inp, "version_not_applicable", False) is not True:
        return None
    reason = getattr(inp, "version_reason", None)
    if isinstance(reason, str) and reason.strip():
        return reason.strip()
    return None


def saturation_from_measurement(rounds, delta):
    """True only when both measurements exist and meet the saturation rule.

    Required rounds are 3 and the delta threshold is 2%. A missing round
    count or a missing delta was not observed, so it is not saturated.
    """
    if rounds is None or delta is None:
        return False
    return rounds >= 3 and delta <= 0.02


def evaluate_stopping_gate(inp: StoppingEvaluationInput) -> StoppingDecision:
    """Evaluate whether an auto-research loop must STOP, DEEPEN, PAUSE, or ABSTAIN.
    
    Formula:
    Gt = RequiredCoverage ∧ EvidenceAdequacy ∧ RequiredExecution ∧ 
         CounterevidenceCoverage ∧ VersionValidity ∧ NoBlockingContradiction
         
    STOP_sufficient = Gt ∧ St ∧ DecisionStable ∧ NoMaterialProbeRemaining ∧ ValidIndependentReview
    """
    minimum_sources = _require_minimum_sources(inp.minimum_independent_sources)
    na_reason = version_not_applicable_reason(inp)
    if getattr(inp, "version_not_applicable", False) is True:
        # A declaration is judged by its reason alone; the matched flag cannot rescue it.
        version_ok = na_reason is not None
    else:
        version_ok = bool_or_absent(inp, "is_target_version_matched", absent=False)
    version_note = f"not applicable: {na_reason}" if na_reason is not None else None
    probe_remaining = bool_or_absent(inp, "has_viable_probe_remaining", absent=True)

    # 1. Check if blocked
    if inp.is_blocked or (not probe_remaining and inp.required_claims_verified < inp.required_claims_total):
        if inp.is_blocked:
            return StoppingDecision(
                state=TerminationState.ABSTAIN_BLOCKED,
                reason=f"Blocked by upstream environment: {inp.block_reason or 'No viable probe available.'}",
                hard_gates_passed=False,
                saturation_passed=False,
                version_note=version_note,
            )

    # 2. Hard Gate Evaluation (Score cannot compensate for a broken hard gate)
    coverage_ok = (inp.required_claims_total > 0) and (inp.required_claims_verified >= inp.required_claims_total)
    sources_ok = inp.independent_sources_count >= minimum_sources
    execution_ok = inp.has_execution_proof
    counterevidence_ok = inp.has_counterevidence_searched
    no_contradiction_ok = inp.unresolved_contradictions_count == 0

    hard_gates_passed = (
        coverage_ok and
        sources_ok and
        execution_ok and
        counterevidence_ok and
        version_ok and
        no_contradiction_ok
    )

    # 3. Saturation Evaluation (measured rounds >= 3 and measured delta <= 2%)
    saturation_passed = saturation_from_measurement(
        inp.consecutive_low_delta_rounds,
        inp.last_weighted_delta,
    )

    # 4. STOP_SUFFICIENT only when every conjunct holds (fail closed).
    if (
        hard_gates_passed
        and saturation_passed
        and not probe_remaining
        and inp.independent_review_passed
    ):
        parts = [
            "All hard gates satisfied",
            "semantic saturation reached (<=2% across >=3 rounds)",
        ]
        if inp.independent_review_passed:
            parts.append("independent review passed")
        certificate = {
            "decision": TerminationState.STOP_SUFFICIENT.value,
            "verified_claims": f"{inp.required_claims_verified}/{inp.required_claims_total}",
            "independent_sources": inp.independent_sources_count,
            "saturation_rounds": inp.consecutive_low_delta_rounds,
            "last_delta": inp.last_weighted_delta,
            "independent_review": inp.independent_review_passed,
        }
        return StoppingDecision(
            state=TerminationState.STOP_SUFFICIENT,
            reason=", ".join(parts) + ".",
            hard_gates_passed=True,
            saturation_passed=True,
            certificate=certificate,
            version_note=version_note,
        )

    # 5. Check Budget
    if inp.remaining_budget_calls <= 0:
        return StoppingDecision(
            state=TerminationState.PAUSE_BUDGET,
            reason="Research budget exhausted while required evidence is still incomplete. Stopping without certifying sufficiency.",
            hard_gates_passed=hard_gates_passed,
            saturation_passed=saturation_passed,
            version_note=version_note,
        )

    # 6. Default: Deepen targeted probe
    reasons = []
    if not coverage_ok:
        reasons.append(f"Missing verified claims ({inp.required_claims_verified}/{inp.required_claims_total})")
    if not sources_ok:
        reasons.append(
            f"Insufficient independent sources ({inp.independent_sources_count} < {inp.minimum_independent_sources})"
        )
    if not execution_ok:
        reasons.append("Missing code execution / test verification proof")
    if not counterevidence_ok:
        reasons.append("Counterevidence and failure modes not yet searched")
    if not version_ok:
        if getattr(inp, "version_not_applicable", False) is True:
            reasons.append("Version declared not applicable but version_reason is missing")
        else:
            reasons.append("Target library/framework version mismatch")
    if not no_contradiction_ok:
        reasons.append(f"Unresolved contradictions ({inp.unresolved_contradictions_count})")
    if not saturation_passed:
        rounds_text = (
            "missing" if inp.consecutive_low_delta_rounds is None else inp.consecutive_low_delta_rounds
        )
        delta_text = (
            "missing" if inp.last_weighted_delta is None else f"{inp.last_weighted_delta:.1%}"
        )
        reasons.append(
            f"Saturation not yet reached (low-delta rounds {rounds_text}/3, delta {delta_text})"
        )
    if probe_remaining:
        reasons.append("A viable probe remains")
    if not inp.independent_review_passed:
        reasons.append("Independent review has not passed")

    return StoppingDecision(
        state=TerminationState.DEEPEN,
        reason=f"Deficiencies detected: {', '.join(reasons)}. Probing further.",
        hard_gates_passed=hard_gates_passed,
        saturation_passed=saturation_passed,
        version_note=version_note,
    )
