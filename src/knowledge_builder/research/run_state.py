"""`run state set`: typed writes of the measured and declared state.json keys.

Only the keys below can be set. The frozen criteria (required claims, budget,
minimum sources, researcher) are not settable. A bad value exits 1 and leaves
state.json byte-identical.
"""

import json
import math
import os
import re
import sys
from pathlib import Path

from knowledge_builder.containment import ContainmentError
from knowledge_builder.research.ledger import AtomicResearchLedger

APPLICABILITY = ("applicable", "not_applicable")


def _count(raw):
    if re.fullmatch(r"[0-9]+", raw) is None:
        raise ValueError("must be an integer >= 0")
    return int(raw)


def _delta(raw):
    try:
        number = float(raw)
    except ValueError:
        raise ValueError("must be a finite number >= 0") from None
    if not math.isfinite(number) or number < 0:
        raise ValueError("must be a finite number >= 0")
    return number


def _boolean(raw):
    if raw not in ("true", "false"):
        raise ValueError("must be true or false")
    return raw == "true"


def _applicability(raw):
    if raw not in APPLICABILITY:
        raise ValueError("must be applicable or not_applicable")
    return raw


def _text(raw):
    if raw.strip() == "":
        raise ValueError("must be a non-empty string")
    return raw.strip()


SETTERS = {
    "round": _count,
    "consecutive_low_delta_rounds": _count,
    "last_weighted_delta": _delta,
    "has_viable_probe_remaining": _boolean,
    "is_target_version_matched": _boolean,
    "version_applicability": _applicability,
    "version_reason": _text,
    "resolved": _text,
}


def register_state(commands, parser_class):
    state = commands.add_parser("state", help="Typed writes to state.json")
    sub = state.add_subparsers(dest="state_command", required=True, parser_class=parser_class)
    setter = sub.add_parser(
        "set",
        help="Set one measured or declared key: " + ", ".join(sorted(SETTERS)),
    )
    setter.add_argument("--root", required=True, help="External knowledge repository root")
    setter.add_argument("--id", required=True, help="Run id")
    setter.add_argument("--key", required=True, help="One of: " + ", ".join(sorted(SETTERS)))
    setter.add_argument("--value", required=True, help="Value; booleans are true or false")
    setter.set_defaults(func=cmd_run_state_set)


def load_run_state(root, run_id):
    """(ledger, state) for an initialised run. Exits 1 on any refusal."""
    from knowledge_builder.research.run_driver import _contained_run, _fail

    try:
        run_dir = _contained_run(root, run_id)
    except ContainmentError as exc:
        _fail(str(exc))
    if os.path.islink(run_dir / "state.json") or not (run_dir / "state.json").is_file():
        _fail(f"run is not initialized: {run_id}")
    try:
        ledger = AtomicResearchLedger(run_id, base_dir=Path(root) / "_evidence")
        state = ledger.load_state()
    except (ContainmentError, ValueError, OSError) as exc:
        _fail(f"unreadable state: {exc}")
    if not isinstance(state, dict):
        _fail("state.json must be an object")
    return ledger, state


def save_run_state(ledger, state):
    from knowledge_builder.research.run_driver import _fail

    try:
        ledger.save_state(state)
    except (ContainmentError, OSError) as exc:
        _fail(str(exc))


def cmd_run_state_set(args):
    from knowledge_builder.research.run_driver import _fail

    parse = SETTERS.get(args.key)
    if parse is None:
        _fail(f"{args.key} is not a settable key; settable: {', '.join(sorted(SETTERS))}")
    try:
        value = parse(args.value)
    except ValueError as exc:
        _fail(f"{args.key} {exc}: {args.value!r}")
    ledger, state = load_run_state(args.root, args.id)
    state = dict(state)
    if args.key == "resolved":
        current = state.get("resolved")
        current = list(current) if isinstance(current, list) else []
        if value not in current:
            current.append(value)
        state["resolved"] = current
        value = current
    else:
        state[args.key] = value
    save_run_state(ledger, state)
    if state.get("version_applicability") == "not_applicable" and not str(
        state.get("version_reason") or ""
    ).strip():
        print("warning: version_applicability is not_applicable but version_reason is unset; the gate will not pass it", file=sys.stderr)
    print(f"{args.key}={json.dumps(value, ensure_ascii=False)}")
