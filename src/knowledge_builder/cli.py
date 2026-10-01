"""Command Line Interface for Design OS Knowledge Builder."""

import argparse
from pathlib import Path
import json
import sys

from knowledge_builder.contract import UniversalKnowledgeUnit, KnowledgeMetadata, SourceAttribution, ModalityType, TrustTier
from knowledge_builder.processors import process_pdf, process_video, process_image, process_web
from knowledge_builder.research.stopping_gate import evaluate_stopping_gate, StoppingEvaluationInput
from knowledge_builder.research.ledger import AtomicResearchLedger, EvidenceAtom
from knowledge_builder.research.council import run_council_audit


def cmd_ingest(args):
    target = Path(args.target) if Path(args.target).exists() else args.target
    print(f"[*] Ingesting: {target}")

    if str(target).startswith("http://") or str(target).startswith("https://"):
        res = process_web(str(target))
    elif str(target).lower().endswith(".pdf"):
        res = process_pdf(Path(target))
    elif str(target).lower().endswith((".mp4", ".mov", ".mkv", ".avi")):
        res = process_video(Path(target))
    elif str(target).lower().endswith((".png", ".jpg", ".jpeg", ".svg")):
        res = process_image(Path(target))
    else:
        print(f"[-] Unsupported file format: {target}")
        sys.exit(1)

    print(f"[✓] Modality: {res['modality']}")
    print(f"[✓] Source SHA256: {res['sha256']}")
    print(f"[✓] Extracted URI: {res['uri']}")


def cmd_gate(args):
    print(f"[*] Evaluating Stopping Gate for run: {args.run_id}")
    # Sample evaluation using inputs
    inp = StoppingEvaluationInput(
        required_claims_total=args.required,
        required_claims_verified=args.verified,
        independent_sources_count=args.sources,
        has_execution_proof=not args.no_code,
        has_counterevidence_searched=not args.no_counterevidence,
        unresolved_contradictions_count=args.contradictions,
        is_target_version_matched=not args.version_mismatch,
        consecutive_low_delta_rounds=args.rounds,
        last_weighted_delta=args.delta,
        remaining_budget_calls=args.budget,
        has_viable_probe_remaining=args.has_probes,
        independent_review_passed=args.review_passed,
    )
    decision = evaluate_stopping_gate(inp)

    print(f"--------------------------------------------------")
    print(f"Decision: {decision.state.value}")
    print(f"Reason:   {decision.reason}")
    print(f"Hard Gates Passed: {decision.hard_gates_passed}")
    print(f"Saturation Passed: {decision.saturation_passed}")
    if decision.certificate:
        print(f"Certificate: {json.dumps(decision.certificate, indent=2)}")
    print(f"--------------------------------------------------")


def cmd_lint(args):
    path = Path(args.file)
    if not path.exists():
        print(f"[-] File not found: {path}")
        sys.exit(1)

    content = path.read_text(encoding="utf-8")
    errors = []

    # Check mandatory headings
    mandatory = ["## Purpose", "## When to Use / When NOT", "## Core Knowledge Content", "## Failure Modes"]
    for h in mandatory:
        if h not in content:
            errors.append(f"Missing mandatory section: '{h}'")

    # Check ease:source
    if "<!-- ease:source" not in content:
        errors.append("Missing provenance grammar: '<!-- ease:source ... -->'")

    if errors:
        print(f"[-] Lint FAILED with {len(errors)} error(s):")
        for err in errors:
            print(f"    - {err}")
        sys.exit(1)
    else:
        print(f"[✓] Lint PASSED: {path.name} satisfies UKMC.v1 standards.")


def cmd_index(args):
    knowledge_dir = Path(args.dir)
    if not knowledge_dir.exists():
        print(f"[-] Directory not found: {knowledge_dir}")
        sys.exit(1)

    files = list(knowledge_dir.glob("**/*.md"))
    index = []

    for f in files:
        if f.name.upper() == "README.MD":
            continue
        index.append({
            "id": f.stem,
            "path": str(f.relative_to(knowledge_dir)),
            "sha256": "placeholder-hash",
        })

    out_file = knowledge_dir / "index.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)

    print(f"[✓] Compiled machine-readable index with {len(index)} file(s) into: {out_file}")


def main():
    parser = argparse.ArgumentParser(description="Design OS Knowledge Builder CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Ingest
    p_ingest = subparsers.add_parser("ingest", help="Ingest PDF, video, image, or web url")
    p_ingest.add_argument("target", help="Path or URL to ingest")
    p_ingest.set_defaults(func=cmd_ingest)

    # Gate
    p_gate = subparsers.add_parser("gate", help="Evaluate stopping condition gate")
    p_gate.add_argument("--run-id", default="run-001")
    p_gate.add_argument("--required", type=int, default=5)
    p_gate.add_argument("--verified", type=int, default=5)
    p_gate.add_argument("--sources", type=int, default=3)
    p_gate.add_argument("--no-code", action="store_true")
    p_gate.add_argument("--no-counterevidence", action="store_true")
    p_gate.add_argument("--contradictions", type=int, default=0)
    p_gate.add_argument("--version-mismatch", action="store_true")
    p_gate.add_argument("--rounds", type=int, default=3)
    p_gate.add_argument("--delta", type=float, default=0.01)
    p_gate.add_argument("--budget", type=int, default=10)
    p_gate.add_argument("--has-probes", action="store_true")
    p_gate.add_argument("--review-passed", action="store_true", default=True)
    p_gate.set_defaults(func=cmd_gate)

    # Lint
    p_lint = subparsers.add_parser("lint", help="Lint markdown file against UKMC standard")
    p_lint.add_argument("file", help="Path to markdown file")
    p_lint.set_defaults(func=cmd_lint)

    # Index
    p_index = subparsers.add_parser("index", help="Emit machine-readable index.json")
    p_index.add_argument("--dir", default="./knowledge", help="Directory containing knowledge markdown files")
    p_index.set_defaults(func=cmd_index)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
