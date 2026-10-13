"""`query` and `action` subcommands. Registered from cli.py with one hook."""

import json
import sys

from knowledge_builder.ontology.actions import ActionError, run_action
from knowledge_builder.ontology.query import QueryError, run_query
from knowledge_builder.ontology.schema import OntologyError


def cmd_query(args):
    try:
        rows = run_query(
            args.root, object_type=args.object_type, status=args.status, linked_to=args.linked_to,
            link_type=args.link_type, implements=args.implements, where=args.where or (), fields=args.fields,
        )
    except (QueryError, OntologyError) as exc:
        print(f"[-] {exc}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(rows, indent=2))


def cmd_action(args):
    params = {}
    for pair in args.param or []:
        key, sep, value = pair.partition("=")
        if not sep or not key:
            print(f"[-] --param needs key=value, got {pair!r}", file=sys.stderr)
            sys.exit(1)
        params[key] = value
    try:
        record = run_action(args.root, args.name, params)
    except ActionError as exc:
        print(f"[-] action {args.name} rejected, nothing changed: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"[✓] action {args.name}: {', '.join(record['files'])}")


def register_ontology(subparsers, parser_class):
    query = subparsers.add_parser("query", help="Filter objects from index.json (read-only)")
    query.add_argument("--root", required=True, help="External knowledge repository root")
    query.add_argument("--object-type")
    query.add_argument("--status")
    query.add_argument("--linked-to", help="Object id linked from or to the result")
    query.add_argument("--link-type", help="Restrict --linked-to to one link type")
    query.add_argument("--implements", help="Interface the object type implements")
    query.add_argument("--where", action="append", help="key=value on an index field (repeatable)")
    query.add_argument("--fields", help="Comma list of index fields to return")
    query.set_defaults(func=cmd_query)

    action = subparsers.add_parser("action", help="Run a typed, verified, logged local write")
    action.add_argument("name", help="Action type from ontology.yaml (or a default)")
    action.add_argument("--root", required=True, help="External knowledge repository root")
    action.add_argument("--param", action="append", help="key=value (repeatable)")
    action.set_defaults(func=cmd_action)
