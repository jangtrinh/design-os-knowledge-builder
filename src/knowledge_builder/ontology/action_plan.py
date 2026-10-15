"""Turn an action spec plus parameters into staged file edits. Nothing here writes to disk."""

from knowledge_builder.containment import ContainmentError, read_text_inside
from knowledge_builder.ontology import action_edits
from knowledge_builder.ontology.action_defaults import DEFAULT_ACTIONS
from knowledge_builder.ontology.action_edits import EditError
from knowledge_builder.ontology.functions import FUNCTIONS
from knowledge_builder.ontology.object_create import create_object
from knowledge_builder.ontology.schema import KEBAB

BARE_KEYS = {"object", "target", "link_type"}


class ActionError(ValueError):
    """An action cannot run, or its result was rejected."""


def action_spec(ontology, name):
    actions = {**DEFAULT_ACTIONS, **(ontology.action_types or {})}
    if name not in actions:
        available = sorted({*actions, "promote-claim", "set-source"})
        raise ActionError(f"unknown action '{name}'; available: {', '.join(available)}")
    return actions[name]


def parse_params(spec, graph, raw):
    declared = spec.get("parameters") or {}
    for key in raw:
        if key not in declared:
            raise ActionError(f"unknown parameter '{key}'; declared: {', '.join(sorted(declared)) or 'none'}")
    params = {}
    for key, rule in declared.items():
        if key not in raw or raw[key] == "":
            raise ActionError(f"missing parameter '{key}'")
        value, kind = raw[key], (rule or {}).get("type", "string")
        if not isinstance(value, str):
            raise ActionError(f"parameter '{key}' takes one value")
        if kind == "object_id" and graph.get(value) is None:
            raise ActionError(f"parameter '{key}': unknown object '{value}'")
        if kind == "id" and (KEBAB.fullmatch(value) is None or graph.get(value) is not None):
            raise ActionError(f"parameter '{key}': '{value}' must be a new kebab-case id")
        params[key] = value
    return params


def check_criteria(spec, params, ctx):
    for criterion in spec.get("criteria") or []:
        name = criterion["function"]
        args = [params.get(arg, arg) for arg in criterion.get("args") or []]
        if not FUNCTIONS[name](ctx, *args):
            raise ActionError(f"criteria failed: {name}({', '.join(str(a) for a in args)})")


class Stage:
    """Edited file texts keyed by root-relative path, plus ids created by this action."""

    def __init__(self, root, graph):
        self.root, self.graph, self.files, self.created = root, graph, {}, {}

    def rel_of(self, ident):
        if ident in self.created:
            return self.created[ident]
        obj = self.graph.get(ident)
        if obj is None:
            raise ActionError(f"unknown object '{ident}'")
        return obj.rel

    def read(self, rel):
        if rel in self.files:
            return self.files[rel]
        return read_text_inside(self.root / rel, self.root)


def apply_edits(spec, params, stage, ontology):
    for edit in spec.get("edits") or []:
        ((verb, args),) = edit.items()
        resolved = {key: _resolve(key, value, params) for key, value in args.items()}
        try:
            VERBS[verb](stage, resolved, ontology)
        except (EditError, ContainmentError, OSError) as exc:
            raise ActionError(f"edit {verb} failed: {exc}") from exc


def _resolve(key, value, params):
    if isinstance(value, dict):
        return {k: _resolve(k, v, params) for k, v in value.items()}
    if isinstance(value, str) and value.startswith("$"):
        if value[1:] not in params:
            raise ActionError(f"edit refers to undeclared parameter {value}")
        return params[value[1:]]
    if key in BARE_KEYS and value in params:
        return params[value]
    return value


def _set(stage, args, _ontology):
    rel = stage.rel_of(args["object"])
    stage.files[rel] = action_edits.set_key(stage.read(rel), args["key"], args["value"])


def _link(change):
    def apply(stage, args, _ontology):
        rel = stage.rel_of(args["object"])
        stage.files[rel] = change(stage.read(rel), args["link_type"], args["target"])
    return apply


VERBS = {
    "set": _set,
    "add-link": _link(action_edits.add_link),
    "remove-link": _link(action_edits.remove_link),
    "create-object": create_object,
}
