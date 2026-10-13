"""Lifecycle: status experimental|active|deprecated; deprecated needs a resolving superseded_by."""

from knowledge_builder.ontology.objects import format_error

STATUSES = ("experimental", "active", "deprecated")


def lifecycle_failures(_ontology, graph):
    failures = []
    for obj in graph.all:
        if obj.data is None:
            continue
        status = obj.status
        if status not in STATUSES:
            failures.append(format_error(obj.rel, f"status '{status}' is not one of {list(STATUSES)}", "/status"))
            continue
        replacement = obj.data.get("superseded_by")
        if status == "deprecated" and not replacement:
            failures.append(format_error(obj.rel, "superseded_by is required when status is deprecated", "/superseded_by"))
        elif replacement and graph.get(replacement) is None:
            failures.append(format_error(obj.rel, f"superseded_by '{replacement}' does not resolve to an object", "/superseded_by"))
    return failures
