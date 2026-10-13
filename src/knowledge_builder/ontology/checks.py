"""Entry point verify calls: every ontology failure line for a root, `[ERROR] <file> <msg> in /<path>`."""

import sys
from pathlib import Path

from knowledge_builder.ontology.link_checks import link_failures
from knowledge_builder.ontology.lifecycle_checks import lifecycle_failures
from knowledge_builder.ontology.object_checks import object_failures
from knowledge_builder.ontology.objects import format_error, load_graph
from knowledge_builder.ontology.schema import OntologyError, SCHEMA_FILE, load_ontology

LEGACY_WARNING = "[WARN] no ontology.yaml: legacy mode, UKMC.v1 checks only"


def ontology_failures(root):
    root = Path(root)
    try:
        ontology = load_ontology(root)
    except OntologyError as exc:
        return [format_error(SCHEMA_FILE, str(exc).removeprefix(f"{SCHEMA_FILE}: "))]
    if ontology is None:
        print(LEGACY_WARNING, file=sys.stderr)
        return []
    graph = load_graph(root)
    failures = []
    for check in (object_failures, link_failures, lifecycle_failures):
        failures.extend(check(ontology, graph))
    return failures
