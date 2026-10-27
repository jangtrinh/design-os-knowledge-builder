"""Ledger driver for one research run. It does not call a model or the network."""

import json
import os
import sys
from pathlib import Path

from knowledge_builder.containment import (
    ContainmentError,
    create_empty_nofollow,
    ensure_real_dir,
    read_text_nofollow,
    require_inside,
)
from knowledge_builder.research.ledger import AtomicResearchLedger, EvidenceAtom
from knowledge_builder.research.saturation import validate_round_metadata


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
    init.add_argument(
        "--require",
        action="append",
        default=None,
        help="Required claim id, frozen into state.json. Repeat for each id.",
    )
    init.add_argument(
        "--researcher",
        default=None,
        help="Researcher runtime id, frozen into state.json",
    )
    init.set_defaults(func=cmd_run_init)

    record = commands.add_parser("record", help="Append one EvidenceAtom JSON object from stdin")
    record.add_argument("--root", required=True, help="External knowledge repository root")
    record.add_argument("--id", required=True, help="Run id")
    record.set_defaults(func=cmd_run_record)

    status = commands.add_parser("status", help="Print the state.json cursor")
    status.add_argument("--root", required=True, help="External knowledge repository root")
    status.add_argument("--id", required=True, help="Run id")
    status.set_defaults(func=cmd_run_status)

    from knowledge_builder.research.run_state import register_state
    from knowledge_builder.research.saturation import register_measure

    register_measure(commands)
    register_state(commands, parser_class)


def cmd_run_init(args):
    if args.budget < 0:
        _fail("budget must be >= 0")
    required = _required_claim_ids(getattr(args, "require", None))
    researcher = getattr(args, "researcher", None)
    if researcher is not None:
        if not isinstance(researcher, str) or not researcher.strip():
            _fail("researcher runtime must be non-empty")
        researcher = researcher.strip()
    try:
        run_dir = _prepare_run(args.root, args.id)
    except ContainmentError as exc:
        _fail(str(exc))
    if os.path.islink(run_dir / "state.json") or os.path.islink(run_dir / "evidence.jsonl"):
        _fail("refusing symlinked output")
    if (run_dir / "state.json").exists() or (run_dir / "evidence.jsonl").exists():
        _fail(f"run already exists: {args.id}")
    try:
        ledger = AtomicResearchLedger(args.id, base_dir=Path(args.root) / "_evidence")
        ensure_real_dir(ledger.stage_dir / "sources")
        create_empty_nofollow(ledger.evidence_path)
        ledger.save_state(_initial_state(args.id, args.budget, required, researcher))
    except ContainmentError as exc:
        _fail(str(exc))
    print(f"_evidence/{args.id}")


def cmd_run_record(args):
    try:
        run_dir = _contained_run(args.root, args.id)
    except ContainmentError as exc:
        _fail(str(exc))
    evidence = run_dir / "evidence.jsonl"
    if os.path.islink(run_dir / "state.json") or os.path.islink(evidence):
        _fail("refusing symlinked output")
    if not (run_dir / "state.json").is_file() or not evidence.is_file():
        _fail(f"run is not initialized: {args.id}")
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("atom must be a JSON object")
        atom = EvidenceAtom(**data)
        validate_round_metadata(atom.metadata)
        AtomicResearchLedger(args.id, base_dir=Path(args.root) / "_evidence").record_atom(atom)
    except (ContainmentError, TypeError, ValueError, json.JSONDecodeError) as exc:
        _fail(f"invalid atom: {exc}")


def cmd_run_status(args):
    try:
        run_dir = _contained_run(args.root, args.id)
    except ContainmentError as exc:
        _fail(str(exc))
    if os.path.islink(run_dir / "state.json") or not (run_dir / "state.json").is_file():
        _fail(f"run is not initialized: {args.id}")
    try:
        state = AtomicResearchLedger(args.id, base_dir=Path(args.root) / "_evidence").load_state()
    except ContainmentError as exc:
        _fail(str(exc))
    # Printed only. A bad or missing note list never rewrites state.json and
    # is not an input to the stopping gate.
    reported = _entailment_notes_report(run_dir / "review.json")
    if reported:
        state = dict(state)
        state.update(reported)
    print(json.dumps(state, indent=2, ensure_ascii=False))


_ENTAILMENT_NOTES_ERROR = "ignored: entailment_notes must be a list of {claim_id, note} strings"


def _entailment_notes_report(review_path):
    """Validate review.json entailment_notes for status. None when the key is absent.

    A malformed value is reported and dropped. It is data, not a gate input.
    """
    if os.path.islink(review_path) or not review_path.is_file():
        return None
    try:
        review = json.loads(read_text_nofollow(review_path))
    except (ContainmentError, OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(review, dict) or "entailment_notes" not in review:
        return None
    parsed = _parse_entailment_notes(review.get("entailment_notes"))
    if parsed is None:
        return {"entailment_notes_error": _ENTAILMENT_NOTES_ERROR}
    return {"entailment_notes": parsed}


def _parse_entailment_notes(notes):
    if not isinstance(notes, list):
        return None
    parsed = []
    for item in notes:
        if not isinstance(item, dict):
            return None
        claim_id = item.get("claim_id")
        note = item.get("note")
        if not isinstance(claim_id, str) or not isinstance(note, str):
            return None
        parsed.append({"claim_id": claim_id, "note": note})
    return parsed


def _required_claim_ids(raw):
    """Repeatable --require values, in the order given."""
    required = []
    for claim_id in raw or []:
        if (
            not isinstance(claim_id, str)
            or claim_id == ""
            or claim_id in {".", ".."}
            or "/" in claim_id
            or "\\" in claim_id
        ):
            _fail(f"claim id is not a single token: {claim_id}")
        required.append(claim_id)
    return required


def _initial_state(run_id, budget, required_claim_ids=None, researcher_runtime=None):
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
        "required_claim_ids": list(required_claim_ids or []),
        "minimum_independent_sources": 2,
        "last_weighted_delta": None,
        "researcher_runtime": researcher_runtime,
    }


def _run_dir(root, run_id):
    if not isinstance(run_id, str) or run_id in {"", ".", ".."} or "/" in run_id or "\\" in run_id:
        _fail(f"run id is not a single path segment: {run_id}")
    return Path(root) / "_evidence" / run_id


def _contained_run(root, run_id):
    """Return _evidence/<id> without creating it. Refuse a symlink that escapes."""
    run = _run_dir(root, run_id)
    root_path = Path(root)
    evidence = root_path / "_evidence"
    if os.path.islink(evidence):
        raise ContainmentError(f"refusing symlinked output: {evidence}")
    if os.path.islink(run):
        raise ContainmentError(f"refusing symlinked output: {run}")
    if evidence.exists():
        require_inside(evidence, root_path)
    if run.exists():
        require_inside(run, root_path)
    return run


def _prepare_run(root, run_id):
    """Create a real _evidence/<id> inside root. A symlink is refused."""
    _contained_run(root, run_id)
    root_path = Path(root)
    if os.path.islink(root_path) or not root_path.is_dir():
        raise ContainmentError(f"not a directory: {root}")
    evidence = ensure_real_dir(root_path / "_evidence")
    require_inside(evidence, root_path)
    run = ensure_real_dir(evidence / run_id)
    require_inside(run, root_path)
    return run


def _fail(message):
    print(message, file=sys.stderr)
    sys.exit(1)
