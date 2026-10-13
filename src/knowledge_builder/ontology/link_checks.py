"""Link rules: declared type, existing target, matching `to` type, no link to a deprecated target.

Cardinality is documentation only and is never enforced (Palantir does not enforce it).
"""

from knowledge_builder.ontology.link_scope import describe, matches
from knowledge_builder.ontology.objects import format_error


def link_failures(ontology, graph):
    failures = []
    for obj in graph.all:
        items = obj.data.get("link_types") if obj.data else None
        if items is None:
            continue
        if not isinstance(items, list):
            failures.append(format_error(obj.rel, "link_types must be a list", "/link_types"))
            continue
        for index, item in enumerate(items):
            failures.extend(_one(ontology, graph, obj, item, f"/link_types/{index}"))
    return failures


def _one(ontology, graph, obj, item, pointer):
    if not isinstance(item, dict) or set(item) != {"link_type", "target_id"} or not all(
        isinstance(value, str) and value for value in item.values()
    ):
        return [format_error(obj.rel, "link must be {link_type, target_id} strings", pointer)]
    name, target_id = item["link_type"], item["target_id"]
    declared = ontology.link_types.get(name)
    if declared is None:
        return [format_error(obj.rel, f"link_type '{name}' is not declared in ontology.yaml", pointer + "/link_type")]
    path = pointer + "/target_id"
    failures = []
    types = ontology.object_types
    if obj.object_type is not None and not matches(declared["from"], obj.object_type, types):
        failures.append(format_error(obj.rel, f"link_type '{name}' starts from type '{describe(declared['from'])}', not from type '{obj.object_type}'", pointer + "/link_type"))
    target = graph.get(target_id)
    if target is None:
        return failures + [format_error(obj.rel, f"target '{target_id}' does not exist", path)]
    if not matches(declared["to"], target.object_type, types):
        actual = f"a '{target.object_type}'" if target.object_type else "untyped (no object_type)"
        failures.append(format_error(obj.rel, f"target '{target_id}' is {actual}, link_type '{name}' needs '{describe(declared['to'])}'", path))
    if target.status == "deprecated":
        replacement = (target.data or {}).get("superseded_by")
        hint = f"use '{replacement}'" if replacement else "no replacement is recorded"
        failures.append(format_error(obj.rel, f"target '{target_id}' is deprecated: {hint}", path))
    return failures
