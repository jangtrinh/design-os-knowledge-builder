"""Load and validate ontology.yaml. A missing file means legacy mode (returns None)."""

import re
from pathlib import Path

from knowledge_builder.containment import ContainmentError, read_text_inside
from knowledge_builder.ontology.errors import OntologyError
from knowledge_builder.ontology.functions import FUNCTIONS
from knowledge_builder.ontology.link_scope import valid_side
from knowledge_builder.ontology.schema_properties import properties_of
from knowledge_builder.ontology.schema_yaml import SchemaSyntaxError, parse_schema_yaml

SCHEMA_FILE = "ontology.yaml"
KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
EDIT_VERBS = {"create-object", "set", "add-link", "remove-link"}
PARAMETER_TYPES = {"string", "id", "object_id"}
INTERFACE_RULES = {"anchors-match-cited-claims"}
FOLDER = re.compile(r"^[A-Za-z0-9_-]+$")


class Ontology:
    def __init__(self, data):
        self.version = data["version"]
        self.interfaces = data["interfaces"]
        self.object_types = data["object_types"]
        self.link_types = {item["link_type"]: item for item in data["link_types"]}
        self.action_types = data["action_types"]
        self.extra_keys = set(data["extra_keys"])

    def interface_of(self, object_type):
        spec = self.object_types.get(object_type) or {}
        return [self.interfaces[name] for name in spec.get("implements", [])]

    def implementing(self, interface):
        return sorted(name for name, spec in self.object_types.items() if interface in spec.get("implements", []))

    def implements(self, object_type, interface):
        return interface in (self.object_types.get(object_type) or {}).get("implements", [])

    def folder_of(self, object_type):
        return (self.object_types.get(object_type) or {}).get("folder")

    def rules_of(self, object_type):
        return {rule for spec in self.interface_of(object_type) for rule in spec["rules"]}

    def declared_properties(self, object_type):
        return {prop["name"]: prop for prop in (self.object_types.get(object_type) or {}).get("properties", [])}


def load_ontology(root):
    """Return Ontology, or None when root has no ontology.yaml (legacy mode)."""
    path = Path(root) / SCHEMA_FILE
    if not path.is_file():
        return None
    try:
        raw = parse_schema_yaml(read_text_inside(path, Path(root)))
    except (ContainmentError, OSError, UnicodeError, SchemaSyntaxError) as exc:
        raise OntologyError(f"{SCHEMA_FILE}: {exc}") from exc
    return _build(raw)


def _build(raw):
    if not isinstance(raw, dict) or not isinstance(raw.get("version"), str):
        raise OntologyError("ontology.yaml: version is required")
    data = {
        "version": raw["version"],
        "interfaces": _interfaces(raw.get("interfaces")),
        "object_types": {},
        "link_types": [],
        "action_types": None,
        "extra_keys": _strings(raw.get("extra_keys"), "extra_keys"),
    }
    data["object_types"] = _object_types(raw.get("object_types"), data["interfaces"])
    data["link_types"] = _link_types(raw.get("link_types"), data["object_types"], data["interfaces"])
    data["action_types"] = _action_types(raw.get("action_types"))
    return Ontology(data)


def _strings(value, label):
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise OntologyError(f"ontology.yaml: {label} must be a list of strings")
    return list(value)


def _name(value, label):
    if not isinstance(value, str) or KEBAB.fullmatch(value) is None:
        raise OntologyError(f"ontology.yaml: {label} must be kebab-case: {value!r}")
    return value


def _interfaces(raw):
    result = {}
    for name, spec in (raw or {}).items():
        spec = spec or {}
        result[_name(name, "interface name")] = {
            "properties": _strings(spec.get("properties"), f"interfaces.{name}.properties"),
            "sections": _strings(spec.get("sections"), f"interfaces.{name}.sections"),
            "rules": _rules(spec.get("rules"), name),
        }
    return result


def _rules(raw, owner):
    rules = _strings(raw, f"interfaces.{owner}.rules")
    for rule in rules:
        if rule not in INTERFACE_RULES:
            raise OntologyError(f"ontology.yaml: interfaces.{owner}.rules has unknown rule {rule!r}; known: {sorted(INTERFACE_RULES)}")
    return rules


def _folder(value, owner):
    if value is None:
        return None
    if not isinstance(value, str) or FOLDER.fullmatch(value) is None or value.startswith("_"):
        raise OntologyError(f"ontology.yaml: object_types.{owner}.folder must be one plain directory name: {value!r}")
    return value


def _object_types(raw, interfaces):
    if not isinstance(raw, dict) or not raw:
        raise OntologyError("ontology.yaml: object_types must be a non-empty map")
    result = {}
    for name, spec in raw.items():
        _name(name, "object type name")
        if name in interfaces:
            raise OntologyError(f"ontology.yaml: {name} is an interface and cannot also be an object type")
        spec = spec or {}
        implements = _strings(spec.get("implements"), f"object_types.{name}.implements")
        if len(implements) > 1:
            raise OntologyError(f"ontology.yaml: {name} implements {len(implements)} interfaces; at most one parent")
        for parent in implements:
            if parent not in interfaces:
                raise OntologyError(f"ontology.yaml: {name} implements undeclared interface {parent}")
        result[name] = {
            "implements": implements,
            "properties": properties_of(spec.get("properties"), name),
            "folder": _folder(spec.get("folder"), name),
        }
    return result


def _link_types(raw, object_types, interfaces):
    seen = set()
    for item in raw or []:
        if not isinstance(item, dict):
            raise OntologyError("ontology.yaml: link_types entries must be maps")
        name = _name(item.get("link_type"), "link_type")
        if name in seen:
            raise OntologyError(f"ontology.yaml: duplicate link_type {name}")
        seen.add(name)
        for side in ("from", "to"):
            if not valid_side(item.get(side), object_types, interfaces):
                raise OntologyError(f"ontology.yaml: link_type {name} {side} {item.get(side)!r} is not an object type")
    return list(raw or [])


def _action_types(raw):
    """None means: ship the default actions."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise OntologyError("ontology.yaml: action_types must be a map")
    for name, spec in raw.items():
        _name(name, "action type name")
        validate_action(name, spec)
    return raw


def validate_action(name, spec):
    params = (spec or {}).get("parameters") or {}
    for pname, pspec in params.items():
        if (pspec or {}).get("type", "string") not in PARAMETER_TYPES:
            raise OntologyError(f"ontology.yaml: action {name} parameter {pname} has unknown type")
    for crit in spec.get("criteria") or []:
        if crit.get("function") not in FUNCTIONS:
            raise OntologyError(f"ontology.yaml: action {name} uses unknown function {crit.get('function')!r}")
    for edit in spec.get("edits") or []:
        verbs = set(edit) if isinstance(edit, dict) else set()
        if len(verbs) != 1 or not verbs <= EDIT_VERBS:
            raise OntologyError(f"ontology.yaml: action {name} has an unknown edit verb: {sorted(verbs)}")
