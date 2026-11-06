"""Append a reasoned resolution for one contradiction atom.

A blank reason, a missing atom, or an atom that is not a contradiction leaves
state.json unchanged.
"""

import json

from knowledge_builder.containment import ContainmentError
from knowledge_builder.research.run_state import load_run_state, save_run_state


def register_resolve(commands):
    parser = commands.add_parser("resolve", help="Record why a contradiction atom is resolved")
    parser.add_argument("--root", required=True, help="External knowledge repository root")
    parser.add_argument("--id", required=True, help="Run id")
    parser.add_argument("--atom", required=True, help="Contradiction atom id")
    parser.add_argument("--reason", required=True, help="Non-empty reason the contradiction is resolved")
    parser.set_defaults(func=cmd_run_resolve)


def cmd_run_resolve(args):
    from knowledge_builder.research.run_driver import _fail

    reason = args.reason.strip() if isinstance(args.reason, str) else ""
    if reason == "":
        _fail("reason must be a non-empty string")
    ledger, state = load_run_state(args.root, args.id)
    try:
        atoms = ledger.load_atoms()
    except (ContainmentError, OSError, TypeError, ValueError) as exc:
        _fail(f"unreadable ledger: {exc}")
    match = [atom for atom in atoms if atom.id == args.atom]
    if not match:
        _fail(f"atom '{args.atom}' not found")
    atom = match[0]
    if atom.claim_type != "CONTRADICTION":
        _fail(f"atom '{atom.id}' is not a CONTRADICTION")
    state = dict(state)
    current = state.get("resolutions")
    current = list(current) if isinstance(current, list) else []
    current.append({"atom": atom.id, "reason": reason})
    state["resolutions"] = current
    save_run_state(ledger, state)
    print(f"resolved {atom.id} reason={json.dumps(reason, ensure_ascii=False)}")
