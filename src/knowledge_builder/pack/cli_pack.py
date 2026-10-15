"""`pack init|status|check`. Registered from cli.py with one hook."""

import json
import sys

from knowledge_builder.ontology.template_files import TemplateError
from knowledge_builder.ontology_mode import require_ontology
from knowledge_builder.pack.check_pack import check_pack
from knowledge_builder.pack.init_pack import PackError, init_pack
from knowledge_builder.pack.status_report import build_status
from knowledge_builder.pack.status_text import status_text


def _fail(message):
    print(f"[-] {message}", file=sys.stderr)
    sys.exit(1)


def cmd_pack_init(args):
    try:
        run = init_pack(args.root, args.topic, args.run, args.budget, args.require or (), args.researcher)
    except (PackError, TemplateError, OSError) as exc:
        _fail(str(exc))
    print(f"[✓] pack scaffolded in {args.root}: ontology.yaml, claims/, sources/, _templates/, run _evidence/{run}")


def cmd_pack_status(args):
    require_ontology(args.root)
    try:
        report = build_status(args.root, args.run)
    except PackError as exc:
        _fail(str(exc))
    print(json.dumps(report, indent=2) if args.json else status_text(report))


def cmd_pack_check(args):
    require_ontology(args.root)
    try:
        code, lines = check_pack(args.root, args.run)
    except PackError as exc:
        _fail(str(exc))
    print("\n".join(lines))
    sys.exit(code)


def register_pack(subparsers, parser_class):
    pack = subparsers.add_parser("pack", help="Scaffold, report on and check an ontology-first knowledge pack")
    commands = pack.add_subparsers(dest="pack_command", required=True, parser_class=parser_class)

    init = commands.add_parser("init", help="Scaffold a new or empty root: ontology.yaml, templates, claims/, sources/, run")
    init.add_argument("--root", required=True, help="New or empty knowledge root")
    init.add_argument("--topic", required=True, help="What the pack is about")
    init.add_argument("--run", default=None, help="Run id (default: <topic>-<yymmdd>)")
    init.add_argument("--budget", type=int, default=400, help="Call budget frozen into the run (default 400)")
    init.add_argument("--require", action="append", help="Required claim id for the run's gate (repeatable)")
    init.add_argument("--researcher", default=None, help="Researcher runtime id frozen into the run")
    init.set_defaults(func=cmd_pack_init)

    status = commands.add_parser("status", help="One-screen report: objects, coverage, gate, saturation")
    status.add_argument("--root", required=True, help="Pack root")
    status.add_argument("--run", default=None, help="Run id (default: pack.json)")
    status.add_argument("--json", action="store_true", help="Print the report as JSON")
    status.set_defaults(func=cmd_pack_status)

    check = commands.add_parser("check", help="verify --claims, coverage, index freshness and the gate; exit 0 only if verify passes")
    check.add_argument("--root", required=True, help="Pack root")
    check.add_argument("--run", default=None, help="Run id (default: pack.json)")
    check.set_defaults(func=cmd_pack_check)
