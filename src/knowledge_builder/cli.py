"""Command Line Interface for Design OS Knowledge Builder."""

import argparse
from pathlib import Path
import json
import sys

from knowledge_builder.containment import ContainmentError
from knowledge_builder.contract import UniversalKnowledgeUnit, KnowledgeMetadata, SourceAttribution, ModalityType, TrustTier
from knowledge_builder.processors import process_pdf, process_video, process_image, process_web
from knowledge_builder.research.council import run_council_audit
from knowledge_builder.research.ledger import AtomicResearchLedger, EvidenceAtom
from knowledge_builder.research.ledger_gate import LedgerGateError, ledger_evaluation_input
from knowledge_builder.research.stopping_gate import (
    evaluate_stopping_gate,
    StoppingEvaluationInput,
    TerminationState,
)
from knowledge_builder.index import cmd_index
from knowledge_builder.ontology_mode import add_legacy_flag, require_ontology
from knowledge_builder.research.run_driver import register_run
from knowledge_builder.verify import cmd_verify


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def gate_exit_code(state, *, self_reported=False):
    """0 stop, 2 deepen, 3 pause, 4 abstain. Self-report must not exit 0."""
    code = {
        TerminationState.STOP_SUFFICIENT: 0,
        TerminationState.DEEPEN: 2,
        TerminationState.PAUSE_BUDGET: 3,
        TerminationState.ABSTAIN_BLOCKED: 4,
    }[state]
    if self_reported and code == 0:
        return 2
    return code


def cmd_freeze(args):
    from knowledge_builder.processors.web_freeze import FreezeError, freeze_web_source
    from knowledge_builder.research.run_driver import _contained_run

    if not args.root or not args.run or not args.stem:
        print("[-] --freeze needs --root, --run and --stem", file=sys.stderr)
        sys.exit(1)
    try:
        _contained_run(args.root, args.run)
        rel, digest, chars = freeze_web_source(args.target, args.root, args.run, args.stem)
    except (FreezeError, ContainmentError) as exc:
        print(f"[-] {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"[✓] Frozen {chars} chars of text from {args.target}")
    print(f"[✓] Source SHA256: {digest}")
    print(f"[✓] Path: {rel}")


def cmd_ingest(args):
    if args.freeze:
        return cmd_freeze(args)
    raw = args.target
    target = Path(raw) if Path(raw).exists() else raw
    print(f"[*] Ingesting: {target}")

    try:
        if str(target).startswith("http://") or str(target).startswith("https://"):
            res = process_web(str(target))
        elif str(target).lower().endswith(".pdf"):
            res = process_pdf(target if isinstance(target, Path) else Path(target))
        elif str(target).lower().endswith((".mp4", ".mov", ".mkv", ".avi")):
            out = Path(args.out) if args.out else None
            res = process_video(target if isinstance(target, Path) else Path(target), output_dir=out)
        elif str(target).lower().endswith((".png", ".jpg", ".jpeg", ".svg")):
            res = process_image(target if isinstance(target, Path) else Path(target))
        else:
            print(f"[-] Unsupported file format: {target}")
            sys.exit(1)
    except RuntimeError as exc:
        print(f"[-] {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"[✓] Modality: {res['modality']}")
    print(f"[✓] Source SHA256: {res['sha256']}")
    print(f"[✓] Extracted URI: {res['uri']}")


def cmd_gate(args):
    # --self-report and the legacy path with no --root cannot exit 0.
    self_reported = True
    if args.self_report or not args.root:
        inp = StoppingEvaluationInput(
            required_claims_total=args.required,
            required_claims_verified=args.verified,
            independent_sources_count=args.sources,
            # Qualitative proofs default false. The negative flags cannot grant them.
            has_execution_proof=False,
            has_counterevidence_searched=False,
            unresolved_contradictions_count=args.contradictions,
            is_target_version_matched=False,
            consecutive_low_delta_rounds=args.rounds,
            last_weighted_delta=args.delta,
            remaining_budget_calls=args.budget,
            has_viable_probe_remaining=args.has_probes,
            independent_review_passed=False,
        )
    else:
        require_ontology(args.root, getattr(args, "legacy", False))
        try:
            inp = ledger_evaluation_input(args.root, args.run_id)
        except LedgerGateError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)
        self_reported = False

    print(f"[*] Evaluating Stopping Gate for run: {args.run_id}")
    decision = evaluate_stopping_gate(inp)
    print(f"--------------------------------------------------")
    print(f"Decision: {decision.state.value}")
    print(f"Reason:   {decision.reason}")
    print(f"Hard Gates Passed: {decision.hard_gates_passed}")
    print(f"Saturation Passed: {decision.saturation_passed}")
    if decision.version_note:
        print(f"Version:  {decision.version_note}")
    if decision.certificate:
        print(f"Certificate: {json.dumps(decision.certificate, indent=2)}")
    print(f"--------------------------------------------------")
    sys.exit(gate_exit_code(decision.state, self_reported=self_reported))


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


def main():
    parser = _Parser(description="Design OS Knowledge Builder CLI")
    subparsers = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)

    # Ingest
    p_ingest = subparsers.add_parser("ingest", help="Ingest PDF, video, image, or web url")
    p_ingest.add_argument("target", help="Path or URL to ingest")
    p_ingest.add_argument(
        "--out",
        default=None,
        help="Directory for video extracts. Required for video; writes nowhere else.",
    )
    p_ingest.add_argument(
        "--freeze",
        action="store_true",
        help="Web url only: write its plain text to _evidence/<run>/sources/<stem>.txt (needs --root, --run, --stem)",
    )
    p_ingest.add_argument("--root", default=None, help="With --freeze: knowledge root")
    p_ingest.add_argument("--run", default=None, help="With --freeze: run id")
    p_ingest.add_argument("--stem", default=None, help="With --freeze: kebab-case file stem")
    p_ingest.set_defaults(func=cmd_ingest)

    # Gate
    p_gate = subparsers.add_parser("gate", help="Evaluate stopping condition gate")
    p_gate.add_argument("--root", default=None, help="Knowledge root. With --run-id, counts come from the ledger.")
    p_gate.add_argument("--run-id", default="run-001")
    p_gate.add_argument("--self-report", action="store_true", help="Integer flags only. Cannot exit 0.")
    p_gate.add_argument("--required", type=int, default=5)
    p_gate.add_argument("--verified", type=int, default=0)
    p_gate.add_argument("--sources", type=int, default=3)
    p_gate.add_argument("--no-code", action="store_true")
    p_gate.add_argument("--no-counterevidence", action="store_true")
    p_gate.add_argument("--contradictions", type=int, default=0)
    p_gate.add_argument("--version-mismatch", action="store_true")
    p_gate.add_argument("--rounds", type=int, default=None)
    p_gate.add_argument("--delta", type=float, default=None)
    p_gate.add_argument("--budget", type=int, default=10)
    p_gate.add_argument("--has-probes", action="store_true")
    add_legacy_flag(p_gate)
    p_gate.set_defaults(func=cmd_gate)

    # Lint
    p_lint = subparsers.add_parser("lint", help="Lint markdown file against UKMC standard")
    p_lint.add_argument("file", help="Path to markdown file")
    p_lint.set_defaults(func=cmd_lint)

    p_verify = subparsers.add_parser("verify", help="Verify markdown provenance under a knowledge root")
    p_verify.add_argument("root", help="External knowledge repository root")
    p_verify.add_argument(
        "--claims",
        action="store_true",
        help="Require each anchor quote to occur in the hashed file. Structural verify stays the default.",
    )
    add_legacy_flag(p_verify)
    p_verify.set_defaults(func=cmd_verify)

    # Index
    p_index = subparsers.add_parser("index", help="Emit machine-readable index.json")
    p_index.add_argument("--root", required=True, help="External knowledge repository root")
    p_index.add_argument(
        "--exclude",
        action="append",
        default=None,
        help="Root-relative glob to skip (default: _evidence/**)",
    )
    add_legacy_flag(p_index)
    p_index.set_defaults(func=cmd_index)

    register_run(subparsers, _Parser)
    from knowledge_builder.cli_ontology import register_ontology

    register_ontology(subparsers, _Parser)
    from knowledge_builder.pack.cli_pack import register_pack

    register_pack(subparsers, _Parser)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
