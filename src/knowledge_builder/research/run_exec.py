"""Run a command and freeze stdout plus stderr as a source capture.

The command's own exit code is recorded. This command exits non-zero only
when it could not run or could not write the capture.
"""

import argparse
import hashlib
import os
import shlex
import subprocess
from datetime import datetime, timezone

from knowledge_builder.containment import ContainmentError
from knowledge_builder.processors.web_freeze import STEM, FreezeError, _open_run_sources, _open_sources
from knowledge_builder.research.call_budget import BudgetExhausted, CaptureError, call_with_budget

MAX_CAPTURE_BYTES = 10 * 1024 * 1024


def register_exec(commands):
    parser = commands.add_parser("exec", help="Run a command and freeze its output as a source")
    parser.add_argument("--root", required=True, help="External knowledge repository root")
    parser.add_argument("--id", required=True, help="Run id")
    parser.add_argument("--stem", required=True, help="Kebab-case file stem")
    parser.add_argument("--timeout", type=int, default=300, help="Seconds before the command is killed (default 300)")
    parser.add_argument("argv", nargs=argparse.REMAINDER, help="Command argv after --")
    parser.set_defaults(func=cmd_run_exec)


def _argv(raw):
    argv = list(raw or [])
    if argv and argv[0] == "--":
        argv = argv[1:]
    return argv


def cmd_run_exec(args):
    from knowledge_builder.research.run_driver import _fail

    argv = _argv(getattr(args, "argv", None))
    if not argv:
        _fail("could not run: no command")
    if type(args.timeout) is not int or args.timeout <= 0:
        _fail("timeout must be a positive number of seconds")
    if STEM.fullmatch(args.stem or "") is None:
        _fail("--stem must be kebab-case: lowercase letters, digits, hyphens")
    try:
        _require_initialized(args.root, args.id)
        rel, digest, code = call_with_budget(
            args.root,
            args.id,
            lambda: _run_and_write(args.root, args.id, args.stem, argv, args.timeout),
            origin="executed",
            url=None,
            command=list(argv),
        )
    except BudgetExhausted as exc:
        _fail(str(exc))
    except (FreezeError, CaptureError, ContainmentError, OSError) as exc:
        _fail(str(exc))
    print(f"Path: {rel}")
    print(f"SHA256: {digest}")
    print(f"Exit: {code}")


def _require_initialized(root, run_id):
    run_fd, extra = _open_run_sources(root, run_id)
    for descriptor in [run_fd, *extra]:
        if descriptor is not None:
            os.close(descriptor)


def _run_and_write(root, run_id, stem, argv, timeout):
    try:
        completed = subprocess.run(
            argv,
            shell=False,
            cwd=os.getcwd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise FreezeError("timed out") from exc
    except OSError as exc:
        raise FreezeError(f"could not run: {exc}") from exc
    combined = completed.stdout + completed.stderr
    if len(combined) > MAX_CAPTURE_BYTES:
        combined = combined[:MAX_CAPTURE_BYTES]
    output = combined.decode("utf-8", errors="replace")
    ran = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = f"Command: {shlex.join(argv)}\nExit: {completed.returncode}\nRan: {ran}\n\n{output}".encode("utf-8")
    _write_new(root, run_id, stem, payload)
    rel = f"_evidence/{run_id}/sources/{stem}.txt"
    return rel, hashlib.sha256(payload).hexdigest(), completed.returncode


def _write_new(root, run_id, stem, payload):
    run_fd, extra = _open_run_sources(root, run_id)
    sources_fd = None
    try:
        sources_fd = _open_sources(run_fd)
        name = f"{stem}.txt"
        try:
            fd = os.open(name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o644, dir_fd=sources_fd)
        except FileExistsError:
            raise FreezeError(f"refusing to overwrite frozen source {name}") from None
        except OSError as exc:
            raise FreezeError(f"refusing output {name}: {exc}") from exc
        try:
            view = memoryview(payload)
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise FreezeError(f"could not write {name}")
                view = view[written:]
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        for descriptor in [run_fd, sources_fd, *extra]:
            if descriptor is not None:
                os.close(descriptor)
