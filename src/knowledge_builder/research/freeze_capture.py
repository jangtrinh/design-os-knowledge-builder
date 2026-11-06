"""Freeze one page and append the capture log line that attests it."""

import os

from knowledge_builder.containment import ContainmentError
from knowledge_builder.processors.web_freeze import (
    STEM,
    FreezeError,
    _open_run_sources,
    _validate_url,
    freeze_web_source,
)
from knowledge_builder.research.call_budget import BudgetExhausted, CaptureError, call_with_budget
from knowledge_builder.research.run_driver import _contained_run


def freeze_and_record(args):
    """Return (relative path, sha256, chars). Refuse before any read when the budget is spent."""
    if not args.root or not args.run or not args.stem:
        raise FreezeError("--freeze needs --root, --run and --stem")
    _contained_run(args.root, args.run)
    if STEM.fullmatch(args.stem or "") is None:
        raise FreezeError("--stem must be kebab-case: lowercase letters, digits, hyphens")
    _validate_url(args.target)
    _require_initialized(args.root, args.run)
    from_file = getattr(args, "from_file", None)
    origin = "from-file" if from_file is not None else "fetched"
    written = {}

    def produce():
        if from_file is not None:
            rel, digest, chars = freeze_web_source(
                args.target, args.root, args.run, args.stem, from_file=from_file
            )
        else:
            rel, digest, chars = freeze_web_source(args.target, args.root, args.run, args.stem)
        written["chars"] = chars
        return rel, digest, None

    try:
        rel, digest, _exit = call_with_budget(
            args.root, args.run, produce, origin=origin, url=args.target, command=None
        )
    except BudgetExhausted:
        raise
    except CaptureError as exc:
        raise FreezeError(str(exc)) from exc
    return rel, digest, written["chars"]


def _require_initialized(root, run_id):
    """Open the run directory so a missing run fails before the budget check."""
    run_fd, extra = _open_run_sources(root, run_id)
    for descriptor in [run_fd, *extra]:
        if descriptor is not None:
            os.close(descriptor)


def freeze_error(exc):
    """True for the failures cmd_freeze already reports with a [-] prefix."""
    return isinstance(exc, (FreezeError, ContainmentError, CaptureError))
