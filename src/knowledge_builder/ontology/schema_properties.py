"""Property declarations of an object type in ontology.yaml."""

from knowledge_builder.ontology.errors import OntologyError

PROPERTY_TYPES = {"string", "enum", "integer", "boolean"}


def _strings(value, label):
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise OntologyError(f"ontology.yaml: {label} must be a list of strings")
    return list(value)


def properties_of(raw, owner):
    props = []
    for item in raw or []:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise OntologyError(f"ontology.yaml: {owner} property needs a name")
        kind = item.get("type", "string")
        if kind not in PROPERTY_TYPES:
            raise OntologyError(f"ontology.yaml: {owner}.{item['name']} has unknown type {kind}")
        if kind == "enum" and not _strings(item.get("values"), f"{owner}.{item['name']}.values"):
            raise OntologyError(f"ontology.yaml: {owner}.{item['name']} enum needs values")
        prop = dict(item, type=kind, required=_boolean(item.get("required", "false"), item["name"]))
        for bound in ("min", "max"):
            if bound in item:
                prop[bound] = _integer(item[bound], f"{owner}.{item['name']}.{bound}")
        props.append(prop)
    return props


def _boolean(value, label):
    if value in ("true", True):
        return True
    if value in ("false", False):
        return False
    raise OntologyError(f"ontology.yaml: {label}.required must be true or false")


def _integer(value, label):
    try:
        return int(value)
    except (TypeError, ValueError):
        raise OntologyError(f"ontology.yaml: {label} must be an integer") from None
