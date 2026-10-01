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
    
    # Saturation metrics
    consecutive_low_delta_rounds: int  # Threshold: >= 3
    last_weighted_delta: float         # Threshold: <= 0.02 (2%)
    
    # Budget & operational state
    remaining_budget_calls: int
    has_viable_probe_remaining: bool
    is_blocked: bool = False
    block_reason: Optional[str] = None
    independent_review_passed: bool = False


@dataclass
class StoppingDecision:
    state: TerminationState
    reason: str
    hard_gates_passed: bool
    saturation_passed: bool
    certificate: Optional[Dict[str, Any]] = None


def evaluate_stopping_gate(inp: StoppingEvaluationInput) -> StoppingDecision:
    """Evaluate whether an auto-research loop must STOP, DEEPEN, PAUSE, or ABSTAIN.
    
    Formula:
    Gt = RequiredCoverage ∧ EvidenceAdequacy ∧ RequiredExecution ∧ 
         CounterevidenceCoverage ∧ VersionValidity ∧ NoBlockingContradiction
         
    STOP_sufficient = Gt ∧ St ∧ DecisionStable ∧ NoMaterialProbeRemaining ∧ ValidIndependentReview
    """
    # 1. Check if blocked
    if inp.is_blocked or (not inp.has_viable_probe_remaining and inp.required_claims_verified < inp.required_claims_total):
        if inp.is_blocked:
            return StoppingDecision(
                state=TerminationState.ABSTAIN_BLOCKED,
                reason=f"Blocked by upstream environment: {inp.block_reason or 'No viable probe available.'}",
                hard_gates_passed=False,
                saturation_passed=False,
            )

    # 2. Hard Gate Evaluation (Score cannot compensate for a broken hard gate)
    coverage_ok = (inp.required_claims_total > 0) and (inp.required_claims_verified >= inp.required_claims_total)
    sources_ok = inp.independent_sources_count >= 2
    execution_ok = inp.has_execution_proof
    counterevidence_ok = inp.has_counterevidence_searched
    version_ok = inp.is_target_version_matched
    no_contradiction_ok = inp.unresolved_contradictions_count == 0

    hard_gates_passed = (
        coverage_ok and
        sources_ok and
        execution_ok and
        counterevidence_ok and
        version_ok and
        no_contradiction_ok
    )

    # 3. Saturation Evaluation (3 rounds with delta <= 2%)
    saturation_passed = (
        inp.consecutive_low_delta_rounds >= 3 and
        inp.last_weighted_delta <= 0.02
    )

    # 4. Check if STOP_SUFFICIENT criteria met
    if hard_gates_passed and saturation_passed:
        if not inp.has_viable_probe_remaining or inp.independent_review_passed:
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
                reason="All hard gates satisfied, semantic saturation reached (<=2% across >=3 rounds), independent review passed.",
                hard_gates_passed=True,
                saturation_passed=True,
                certificate=certificate,
            )

    # 5. Check Budget
    if inp.remaining_budget_calls <= 0:
        return StoppingDecision(
            state=TerminationState.PAUSE_BUDGET,
            reason="Research budget exhausted while required evidence is still incomplete. Stopping without certifying sufficiency.",
            hard_gates_passed=hard_gates_passed,
            saturation_passed=saturation_passed,
        )

    # 6. Default: Deepen targeted probe
    reasons = []
    if not coverage_ok:
        reasons.append(f"Missing verified claims ({inp.required_claims_verified}/{inp.required_claims_total})")
    if not sources_ok:
        reasons.append(f"Insufficient independent sources ({inp.independent_sources_count} < 2)")
    if not execution_ok:
        reasons.append("Missing code execution / test verification proof")
    if not counterevidence_ok:
        reasons.append("Counterevidence and failure modes not yet searched")
    if not version_ok:
        reasons.append("Target library/framework version mismatch")
    if not no_contradiction_ok:
        reasons.append(f"Unresolved contradictions ({inp.unresolved_contradictions_count})")
    if not saturation_passed:
        reasons.append(f"Saturation not yet reached (round {inp.consecutive_low_delta_rounds}/3, delta {inp.last_weighted_delta:.1%})")

    return StoppingDecision(
        state=TerminationState.DEEPEN,
        reason=f"Deficiencies detected: {', '.join(reasons)}. Probing further.",
        hard_gates_passed=hard_gates_passed,
        saturation_passed=saturation_passed,
    )
