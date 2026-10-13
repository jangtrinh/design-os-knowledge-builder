"""`query` and `action` subcommands. Registered from cli.py with one hook."""

import json
import sys

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
