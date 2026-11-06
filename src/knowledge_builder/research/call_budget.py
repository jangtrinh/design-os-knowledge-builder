"""Spend one research call under the ledger lock, and give it back if the capture is not logged.

A call is one successful ingest --freeze or run exec. At zero remaining the
work is refused before any fetch or process starts.
"""

import fcntl
import os
from pathlib import Path

from knowledge_builder.containment import ContainmentError
from knowledge_builder.research.capture_log import append_record, make_record
from knowledge_builder.research.ledger import AtomicResearchLedger


class BudgetExhausted(Exception):
    """No calls remain. The stopping gate will pause."""


class CaptureError(Exception):
    """The capture could not be logged. The call was refunded."""


def _whole(value):
    """A non-bool int, or None when the field is missing or the wrong type."""
    if type(value) is not int:
        return None
    return value


def exhausted_message(state):
    used = _whole(state.get("budget_used"))
    total = _whole(state.get("budget_total"))
    return (
        f"budget exhausted (used {0 if used is None else used} of {0 if total is None else total}): "
        "the gate will PAUSE_BUDGET"
    )


def _lock(ledger):
    lock_path = ledger.evidence_path.with_name(ledger.evidence_path.name + ".lock")
    if os.path.islink(lock_path):
        raise ContainmentError(f"refusing symlinked output: {lock_path}")
    from knowledge_builder.containment import open_lock_nofollow

    return open_lock_nofollow(lock_path)


def call_with_budget(root, run_id, produce, *, origin, url, command):
    """Reserve one call, run produce() -> (path, sha256, exit_code), then log it.

    produce runs only while a call remains. A failure refunds the call and
    writes no capture line. exit_code is stored as produce returned it.
    """
    ledger = AtomicResearchLedger(run_id, base_dir=Path(root) / "_evidence")
    lock_fd = _lock(ledger)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        state = ledger.load_state()
        if not isinstance(state, dict):
            raise CaptureError("state.json must be an object")
        remaining = _whole(state.get("remaining_budget_calls"))
        if remaining is None or remaining <= 0:
            raise BudgetExhausted(exhausted_message(state))
        used = _whole(state.get("budget_used"))
        state = dict(state)
        state["remaining_budget_calls"] = remaining - 1
        state["budget_used"] = (0 if used is None else used) + 1
        ledger.save_state(state)
        try:
            rel, digest, exit_code = produce()
            append_record(root, run_id, make_record(rel, digest, origin, url, command, exit_code))
        except BaseException:
            _refund(ledger)
            raise
        return rel, digest, exit_code
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def _refund(ledger):
    state = ledger.load_state()
    if not isinstance(state, dict):
        return
    remaining = _whole(state.get("remaining_budget_calls"))
    used = _whole(state.get("budget_used"))
    state = dict(state)
    if remaining is not None:
        state["remaining_budget_calls"] = remaining + 1
    if used is not None and used > 0:
        state["budget_used"] = used - 1
    ledger.save_state(state)
