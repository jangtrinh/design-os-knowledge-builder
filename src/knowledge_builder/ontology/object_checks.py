"""Per-object checks: object_type, interface contract, property rules, closed key set, unique id."""

import re

from knowledge_builder.anchors import heading_present, visible_lines
from knowledge_builder.ontology.objects import format_error

BASE_KEYS = {
    "id", "title", "domain", "description", "when", "trust_tier", "version",
    "source_attribution", "object_type", "status", "superseded_by", "link_types",
}
_INTEGER = re.compile(r"^-?\d+$")


def object_failures(ontology, graph):
    failures = []
    for ident, group in graph.by_id.items():
        if len(group) > 1:
            failures.extend(format_error(o.rel, f"duplicate id '{ident}'", "/id") for o in group)
    for obj in graph.all:
        if obj.data is None:
            continue
        failures.extend(_one(ontology, obj))
    return failures


def _one(ontology, obj):
    kind = obj.object_type
    if kind is None:
        return [format_error(obj.rel, "object_type is required", "/object_type")]
    if kind in ontology.interfaces:
        return [format_error(obj.rel, f"object_type '{kind}' is an interface, not an object type", "/object_type")]
    if kind not in ontology.object_types:
        return [format_error(obj.rel, f"object_type '{kind}' is not declared in ontology.yaml", "/object_type")]
    failures = _interface(ontology, obj, kind)
    failures += _properties(ontology, obj, kind)
    return failures + _closed_keys(ontology, obj, kind)


def _interface(ontology, obj, kind):
    failures = []
    lines = visible_lines(obj.text)
    for spec in ontology.interface_of(kind):
        for name in spec["properties"]:
            if not _present(obj.data.get(name)):
                failures.append(format_error(obj.rel, f"missing property '{name}'", f"/{name}"))
        for heading in spec["sections"]:
            if not heading_present(lines, _heading_prefix(heading)):
                failures.append(format_error(obj.rel, f"missing section '{_heading_prefix(heading)}'", "/body"))
    return failures


def _heading_prefix(heading):
    """`## Failure Modes (Mandatory)` is satisfied by `## Failure Modes`, as in UKMC.v1 verify."""
    return heading.removesuffix(" (Mandatory)")


def _present(value):
    return value is not None and value != "" and value != []


def _properties(ontology, obj, kind):
    failures = []
    for name, prop in ontology.declared_properties(kind).items():
        value = obj.data.get(name)
        if not _present(value):
            if prop["required"]:
                failures.append(format_error(obj.rel, f"missing property '{name}'", f"/{name}"))
            continue
        problem = _value_problem(prop, value)
        if problem:
            failures.append(format_error(obj.rel, f"{name} {problem}", f"/{name}"))
    return failures


def _value_problem(prop, value):
    kind = prop["type"]
    if kind == "enum":
        return None if value in prop["values"] else f"{value!r} is not one of {prop['values']}"
    if kind == "boolean":
        return None if value in ("true", "false") else f"{value!r} is not true or false"
    if kind == "integer":
        if not isinstance(value, str) or _INTEGER.fullmatch(value) is None:
            return f"{value!r} is not an integer"
        number = int(value)
        if number < prop.get("min", number) or number > prop.get("max", number):
            return f"{number} is outside {prop.get('min', '-inf')}..{prop.get('max', 'inf')}"
        return None
    return None if isinstance(value, str) else f"{value!r} is not a string"


def _closed_keys(ontology, obj, kind):
    allowed = BASE_KEYS | ontology.extra_keys | set(ontology.declared_properties(kind))
    for spec in ontology.interface_of(kind):
        allowed |= set(spec["properties"])
    return [
        format_error(obj.rel, f"unknown key '{key}'", f"/{key}")
        for key in obj.data
        if key not in allowed
    ]
