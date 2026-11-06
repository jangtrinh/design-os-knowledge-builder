"""Re-fetch every logged capture an atom cites and record which quotes are still on the page.

The command writes review.json. It does not write sources and it does not
spend a call. A page that cannot be fetched is recorded as unreachable.
The verdict is stored; it is not the exit code.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from knowledge_builder.containment import ContainmentError, atomic_write
from knowledge_builder.research.capture_log import load_captures
from knowledge_builder.research.live_sources import live_source_findings
from knowledge_builder.research.review_check import claims_digest, digest_file


def register_review(commands):
    parser = commands.add_parser(
        "review",
        help="Re-fetch logged captures and bind review.json to the ledger",
    )
    parser.add_argument("--root", required=True, help="External knowledge repository root")
    parser.add_argument("--id", required=True, help="Run id")
    parser.add_argument("--reviewer", required=True, help="Runtime that performed the review")
    parser.add_argument("--verdict", required=True, choices=("pass", "fail"), help="pass or fail")
    parser.add_argument("--note", default="", help="Optional note stored with the review")
    parser.add_argument(
        "--confirm-version-na",
        action="store_true",
        help="Confirm that version applicability not_applicable is honest",
    )
    parser.add_argument(
        "--confirm-execution-na",
        action="store_true",
        help="Confirm that execution applicability not_applicable is honest",
    )
    parser.set_defaults(func=cmd_run_review)


def cmd_run_review(args):
    from knowledge_builder.research.capture_log import CaptureLogError
    from knowledge_builder.research.run_driver import _fail
    from knowledge_builder.research.run_state import load_run_state

    reviewer = args.reviewer.strip() if isinstance(args.reviewer, str) else ""
    if reviewer == "":
        _fail("reviewer runtime must be non-empty")
    ledger, state = load_run_state(args.root, args.id)
    researcher = state.get("researcher_runtime")
    if isinstance(researcher, str) and researcher.strip() and reviewer == researcher.strip():
        _fail("reviewer runtime equals the researcher runtime")
    try:
        atoms = ledger.load_atoms()
        rows = load_captures(args.root, args.id)
    except (CaptureLogError, ContainmentError, OSError, UnicodeError, ValueError) as exc:
        _fail(f"unreadable ledger: {exc}")
    sources = live_source_findings(args.root, args.id, rows, atoms)
    run = Path(args.root) / "_evidence" / args.id
    ledger_sha = digest_file(run / "evidence.jsonl")
    captures_sha = digest_file(run / "captures.jsonl")
    if ledger_sha is None or captures_sha is None:
        _fail("unreadable ledger: refusing a symlinked evidence file")
    document = {
        "reviewer_runtime": reviewer,
        "verdict": args.verdict,
        "note": args.note if isinstance(args.note, str) else "",
        "reviewed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ledger_sha256": ledger_sha,
        "captures_sha256": captures_sha,
        "claims_sha256": claims_digest(args.root),
        "confirm_version_na": args.confirm_version_na is True,
        "confirm_execution_na": args.confirm_execution_na is True,
        "sources": sources,
    }
    payload = (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    try:
        atomic_write(run, "review.json", payload)
    except (ContainmentError, OSError) as exc:
        _fail(str(exc))
    for row in sources:
        print(f"{row['path']} {row['status']} quotes {row['quotes_found']}/{row['quotes_total']}")
