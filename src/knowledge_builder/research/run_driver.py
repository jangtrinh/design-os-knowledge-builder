"""Ledger driver for one research run. It does not call a model or the network."""

import json
import sys
from pathlib import Path

from knowledge_builder.research.ledger import AtomicResearchLedger, EvidenceAtom


def register_run(subparsers, parser_class):
    run = subparsers.add_parser(
        "run",
        help="Init, record, and status for one evidence ledger",
    )
    commands = run.add_subparsers(dest="run_command", required=True, parser_class=parser_class)

    init = commands.add_parser(
        "init",
        help="Create _evidence/<id>/{state.json,evidence.jsonl,sources/}",
    )
    init.add_argument("--root", required=True, help="External knowledge repository root")
    init.add_argument("--id", required=True, help="Run id (one path segment)")
    init.add_argument("--budget", required=True, type=int, help="Call budget frozen into state.json")
    init.set_defaults(func=cmd_run_init)

    record = commands.add_parser("record", help="Append one EvidenceAtom JSON object from stdin")
    record.add_argument("--root", required=True, help="External knowledge repository root")
    record.add_argument("--id", required=True, help="Run id")
    record.set_defaults(func=cmd_run_record)

    status = commands.add_parser("status", help="Print the state.json cursor")
    status.add_argument("--root", required=True, help="External knowledge repository root")
    status.add_argument("--id", required=True, help="Run id")
    status.set_defaults(func=cmd_run_status)


def cmd_run_init(args):
    if args.budget < 0:
        _fail("budget must be >= 0")
    run_dir = _run_dir(args.root, args.id)
    if (run_dir / "state.json").exists() or (run_dir / "evidence.jsonl").exists():
        _fail(f"run already exists: {args.id}")
    ledger = AtomicResearchLedger(args.id, base_dir=Path(args.root) / "_evidence")
    (ledger.stage_dir / "sources").mkdir(parents=True, exist_ok=True)
    ledger.evidence_path.write_bytes(b"")
    ledger.save_state(_initial_state(args.id, args.budget))
    print(f"_evidence/{args.id}")


def cmd_run_record(args):
    run_dir = _run_dir(args.root, args.id)
    evidence = run_dir / "evidence.jsonl"
    if not (run_dir / "state.json").is_file() or not evidence.is_file():
        _fail(f"run is not initialized: {args.id}")
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("atom must be a JSON object")
        atom = EvidenceAtom(**data)
        AtomicResearchLedger(args.id, base_dir=Path(args.root) / "_evidence").record_atom(atom)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        _fail(f"invalid atom: {exc}")


def cmd_run_status(args):
    run_dir = _run_dir(args.root, args.id)
    if not (run_dir / "state.json").is_file():
        _fail(f"run is not initialized: {args.id}")
    state = AtomicResearchLedger(args.id, base_dir=Path(args.root) / "_evidence").load_state()
    print(json.dumps(state, indent=2, ensure_ascii=False))


def _initial_state(run_id, budget):
    """Cursor frozen at init. Later commands may add atoms; they do not rewrite these criteria."""
    return {
        "run_id": run_id,
        "round": 0,
        "status": "RUNNING",
        "budget_used": 0,
        "budget_total": budget,
        "remaining_budget_calls": budget,
        "gaps": [],
        "resolved": [],
        "required_claim_ids": [],
        "minimum_independent_sources": 2,
        "last_weighted_delta": None,
        "researcher_runtime": None,
    }


def _run_dir(root, run_id):
    if not isinstance(run_id, str) or run_id in {"", ".", ".."} or "/" in run_id or "\\" in run_id:
        _fail(f"run id is not a single path segment: {run_id}")
    return Path(root) / "_evidence" / run_id


def _fail(message):
    print(message, file=sys.stderr)
    sys.exit(1)
