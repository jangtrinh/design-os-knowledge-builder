"""Parameters of the default create-object action: derived from the object type, not a fixed list."""

from knowledge_builder.ontology.action_defaults import DEFAULT_ACTIONS
from knowledge_builder.ontology.action_plan import ActionError
from knowledge_builder.ontology.object_checks import value_problem
from knowledge_builder.ontology.schema import KEBAB

ALWAYS = ("id", "object_type", "title")
DOCUMENT = ("domain", "description", "when", "source")
REPEATABLE = {"when", "source"}


def is_default(ontology):
    return "create-object" not in (ontology.action_types or {})


def reject_repeated(items):
    """Only the default create-object takes a repeated parameter."""
    for raw in items:
        for key, value in raw.items():
            if not isinstance(value, str):
                raise ActionError(f"parameter '{key}' takes one value")


def prepare(ontology, graph, raw):
    """(spec, params) for one create-object call. `when` and `source` become lists; declared properties are validated."""
    kind = raw.get("object_type")
    if kind in (None, "", []):
        raise ActionError("missing parameter 'object_type'")
    if not isinstance(kind, str) or kind not in ontology.object_types:
        raise ActionError(f"parameter 'object_type': '{kind}' is not declared; declared: {', '.join(sorted(ontology.object_types))}")
    accepted = _accepted(ontology, kind)
    for key in raw:
        if key not in accepted:
            raise ActionError(f"unknown parameter '{key}'; declared: {', '.join(sorted(accepted))}")
    params = {}
    for name, (prop, required) in accepted.items():
        value = raw.get(name)
        if value in (None, "", []):
            if required:
                raise ActionError(f"missing parameter '{name}'")
            continue
        params[name] = _value(name, value, prop, graph)
    values = {name: f"${name}" for name in params if name not in ("id", "object_type")}
    edit = {"create-object": {"id": "$id", "object_type": "$object_type", "values": values}}
    return {**DEFAULT_ACTIONS["create-object"], "parameters": {name: None for name in accepted}, "edits": [edit]}, params


def _accepted(ontology, kind):
    """name -> (declared property or None, required)."""
    accepted = {name: (None, True) for name in ALWAYS}
    if ontology.object_types[kind]["implements"]:
        accepted.update({name: (None, True) for name in DOCUMENT})
    for name, prop in ontology.declared_properties(kind).items():
        accepted[name] = (prop, accepted.get(name, (None, prop["required"]))[1] or prop["required"])
    return accepted


def _value(name, value, prop, graph):
    if name in REPEATABLE:
        items = [value] if isinstance(value, str) else value
        if not all(isinstance(item, str) and item for item in items) or len(set(items)) != len(items):
            raise ActionError(f"parameter '{name}': give each value once, as non-empty text")
        return list(items)
    if not isinstance(value, str):
        raise ActionError(f"parameter '{name}' takes one value")
    if name == "id" and (KEBAB.fullmatch(value) is None or graph.get(value) is not None):
        raise ActionError(f"parameter 'id': '{value}' must be a new kebab-case id")
    problem = value_problem(prop, value) if prop else None
    if problem:
        raise ActionError(f"parameter '{name}': {problem}")
    return value
