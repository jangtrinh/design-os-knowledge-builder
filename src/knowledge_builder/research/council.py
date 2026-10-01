"""The 5-Perspective Audit Council.
Evaluates research findings through 5 distinct expert lenses:
1. Builder (Practical execution & minimal runnable examples)
2. Red-Team (Adversarial edge-cases, failure modes, race conditions)
3. Architect (System design, maintainability, license safety)
4. Auditor (Cost, latency, RAM/CPU footprint)
5. Operator (Observability, debug ergonomics, troubleshooting)
"""

from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class PerspectiveReview:
    persona: str
    status: str  # PASS | WARN | FAIL
    question: str
    finding: str
    evidence_ref: str


def run_council_audit(claims: List[Dict[str, Any]], license_name: str = "MIT") -> Dict[str, Any]:
    reviews = []
    
    # 1. Builder Perspective
    has_runnable_code = any(c.get("verified_by_code", False) for c in claims)
    reviews.append(PerspectiveReview(
        persona="Builder (Pragmatic Execution)",
        status="PASS" if has_runnable_code else "FAIL",
        question="Is there an actual runnable code sample or reproduction test?",
        finding="Code execution confirmed." if has_runnable_code else "No verified code snippets found; purely theoretical.",
        evidence_ref="claims.code_verification",
    ))

    # 2. Red-Team Perspective
    failure_claims = [c for c in claims if c.get("claim_type") == "FAILURE_MODE"]
    has_failures = len(failure_claims) > 0
    reviews.append(PerspectiveReview(
        persona="Red-Team (Adversarial Skeptic)",
        status="PASS" if has_failures else "FAIL",
        question="Have known failure modes, memory leaks, and breaking edge cases been documented?",
        finding=f"Identified {len(failure_claims)} failure modes." if has_failures else "Zero failure modes documented. Critical blindspot.",
        evidence_ref="claims.failure_modes",
    ))

    # 3. Architect Perspective
    is_safe_license = license_name.upper() not in ["GPL", "AGPL", "GPLV3", "AGPLV3"]
    reviews.append(PerspectiveReview(
        persona="Architect (Systems & Governance)",
        status="PASS" if is_safe_license else "FAIL",
        question="Does this introduce architectural debt or infective licenses (GPL/AGPL)?",
        finding=f"License '{license_name}' is permissible." if is_safe_license else f"License '{license_name}' is copyleft/infective. Quarantine required.",
        evidence_ref="source.license",
    ))

    # 4. Auditor Perspective
    has_benchmark = any(c.get("claim_type") == "BENCHMARK" for c in claims)
    reviews.append(PerspectiveReview(
        persona="Auditor (Cost & Performance)",
        status="PASS" if has_benchmark else "WARN",
        question="Are real-world resource costs (p99 latency, RAM, token overhead) benchmarked?",
        finding="Empirical benchmarks present." if has_benchmark else "Lacks concrete resource benchmarks.",
        evidence_ref="claims.benchmarks",
    ))

    # 5. Operator Perspective
    has_observability = any("debug" in c.get("statement", "").lower() or "log" in c.get("statement", "").lower() for c in claims)
    reviews.append(PerspectiveReview(
        persona="Operator (Day-2 Operations)",
        status="PASS" if has_observability else "WARN",
        question="How is this monitored, debugged, and restored when it fails?",
        finding="Operational troubleshooting mentioned." if has_observability else "Limited operational and debugging guidance.",
        evidence_ref="claims.operations",
    ))

    overall_pass = all(r.status in ["PASS", "WARN"] for r in reviews) and not any(r.status == "FAIL" for r in reviews)
    
    return {
        "council_pass": overall_pass,
        "reviews": [r.__dict__ for r in reviews],
    }
