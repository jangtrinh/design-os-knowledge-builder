"""`query` and `action` subcommands. Registered from cli.py with one hook."""

import json
import sys
from pathlib import Path

from knowledge_builder.ontology.actions import ActionError, run_action, run_batch
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


def _batch_items(path):
    items = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except ValueError as exc:
            raise ActionError(f"{path}:{number}: not JSON: {exc}") from exc
        if not isinstance(item, dict):
            raise ActionError(f"{path}:{number}: each line must be a JSON object of string parameters")
        items.append(item)
    if not items:
        raise ActionError(f"{path}: no items")
    return items


def _run_batch(args):
    try:
        records = run_batch(args.root, args.name, _batch_items(args.batch))
    except (ActionError, OSError) as exc:
        print(f"[-] action {args.name} --batch rejected, nothing changed: {exc}", file=sys.stderr)
        sys.exit(1)
    files = sorted({rel for record in records for rel in record["files"]})
    print(f"[✓] action {args.name}: {len(records)} item(s), {len(files)} file(s): {', '.join(files)}")


def cmd_action(args):
    if args.batch:
        return _run_batch(args)
    params = {}
    for pair in args.param or []:
        key, sep, value = pair.partition("=")
        if not sep or not key:
            print(f"[-] --param needs key=value, got {pair!r}", file=sys.stderr)
            sys.exit(1)
        if key in params:
            params[key] = [*params[key], value] if isinstance(params[key], list) else [params[key], value]
        else:
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
    action.add_argument("--param", action="append", help="key=value (repeat a key only where the action takes several values, e.g. create-object when/source)")
    action.add_argument("--batch", help="JSONL file, one parameter object per line (promote-claim): one verify for the whole batch")
    action.set_defaults(func=cmd_action)
