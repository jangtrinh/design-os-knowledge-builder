"""Ontology is the default: a root without ontology.yaml is refused unless the caller passes --legacy."""

import sys
from pathlib import Path

MESSAGE = (
    "no ontology.yaml: run `pack init` for a new pack or `pack migrate` for an existing one; "
    "pass --legacy to check a UKMC.v1 root"
)


def require_ontology(root, legacy=False):
    """Exit 1 when root is an existing directory with no ontology.yaml and legacy is off.

    A path that is not a directory falls through, so each command keeps its own "not found" message.
    """
    path = Path(root).expanduser()
    if legacy or not path.is_dir() or (path / "ontology.yaml").is_file():
        return
    print(f"[-] {MESSAGE}", file=sys.stderr)
    sys.exit(1)


def add_legacy_flag(parser):
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Accept a root with no ontology.yaml and check it as UKMC.v1 (default: refuse it)",
    )
