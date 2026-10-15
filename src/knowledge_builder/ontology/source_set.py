"""set-source: re-attribute the publisher and/or kind of a frozen-source object. Plans edits only.

Native action (the criteria need the object's own type enum), run through the same pipeline as every other action.
"""

from knowledge_builder.ontology.action_edits import EditError, set_key
from knowledge_builder.ontology.action_plan import ActionError, Stage
from knowledge_builder.ontology.claim_state import host_of
from knowledge_builder.ontology.hosting_hosts import is_hosting_host
from knowledge_builder.ontology.source_checks import SOURCE_INTERFACE

PARAMS = {"source", "publisher", "kind"}
EDITED = ("kind", "publisher")


def plan_batch(root, ontology, graph, items):
    """(stage, [(params, stage file texts after that item)]). Items see each other's staged results."""
    stage, steps = Stage(root, graph), []
    for number, raw in enumerate(items, start=1):
        try:
            params = _params(raw)
            _set(ontology, graph, stage, params)
        except (ActionError, EditError) as exc:
            raise ActionError(f"item {number}: {exc}" if len(items) > 1 else str(exc)) from exc
        steps.append((params, dict(stage.files)))
    return stage, steps


def _params(raw):
    for key, value in raw.items():
        if key not in PARAMS:
            raise ActionError(f"unknown parameter '{key}'; declared: {', '.join(sorted(PARAMS))}")
        if not isinstance(value, str):
            raise ActionError(f"parameter '{key}' takes one value")
    if not raw.get("source"):
        raise ActionError("missing parameter 'source'")
    if not any(key in raw for key in EDITED):
        raise ActionError("set-source needs a publisher or a kind to change: --param publisher=<name> and/or --param kind=<kind>")
    return dict(raw)


def _set(ontology, graph, stage, params):
    obj = graph.get(params["source"])
    if obj is None:
        raise ActionError(f"parameter 'source': unknown object '{params['source']}'")
    if not (obj.data and obj.object_type and ontology.implements(obj.object_type, SOURCE_INTERFACE)):
        raise ActionError(f"parameter 'source': '{obj.id}' is not a {SOURCE_INTERFACE} object")
    if "kind" in params:
        allowed = (ontology.declared_properties(obj.object_type).get("kind") or {}).get("values")
        if not params["kind"] or (allowed and params["kind"] not in allowed):
            raise ActionError(f"parameter 'kind': {params['kind']!r} is not one of {'|'.join(allowed or ['a declared kind'])}")
    if "publisher" in params:
        _check_publisher(params["publisher"])
    for key in EDITED:
        if key in params:
            value = params[key].strip()
            stage.files[obj.rel] = set_key(stage.read(obj.rel), key, value)


def _check_publisher(name):
    if not name.strip():
        raise ActionError("parameter 'publisher' must not be blank")
    if is_hosting_host(host_of("//" + name.strip().lower())):
        raise ActionError(
            f"publisher '{name.strip()}' hosts or mirrors other publishers' work, so it cannot be the publisher: "
            "name who wrote the page"
        )
