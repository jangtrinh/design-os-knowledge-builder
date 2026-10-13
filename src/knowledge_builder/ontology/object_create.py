"""The create-object edit: a new object in its type's folder, from a template file or a generated one."""

import hashlib
import json
import re

from knowledge_builder.containment import ContainmentError, read_text_inside, require_inside
from knowledge_builder.ontology.action_defaults import DEFAULT_TEMPLATE, MINIMAL_TEMPLATE
from knowledge_builder.ontology.action_edits import EditError, set_key
from knowledge_builder.ontology.schema import KEBAB

PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")
REPEATING = (frozenset({"when"}), frozenset({"source", "source_sha256"}))
NOT_PROPERTIES = {"id", "object_type", "title", "when", "source", "source_sha256"}


def create_object(stage, args, ontology):
    ident, kind, values = args["id"], args["object_type"], dict(args["values"])
    if kind not in ontology.object_types:
        raise EditError(f"object_type '{kind}' is not declared")
    if KEBAB.fullmatch(str(ident)) is None:
        raise EditError(f"id '{ident}' must be kebab-case")
    folder = ontology.folder_of(kind)
    rel = f"{folder}/{ident}.md" if folder else f"{ident}.md"
    if (stage.root / rel).exists() or rel in stage.files:
        raise EditError(f"{rel} already exists")
    template = _template(stage.root, ontology, kind)
    values.update(id=ident, object_type=kind)
    for key in ("when", "source"):
        if key in values:
            values[key] = [values[key]] if isinstance(values[key], str) else list(values[key])
    if "{{source}}" in template or "source" in values:
        values["source_sha256"] = [_digest(stage.root, source) for source in values.get("source") or [""]]
    text = _render(template, values)
    for name in ontology.declared_properties(kind):
        if name in values and name not in NOT_PROPERTIES and "{{" + name + "}}" not in template:
            text = set_key(text, name, str(values[name]))
    stage.files[rel] = text
    stage.created[ident] = rel


def _digest(root, source):
    try:
        target = require_inside(root / source, root)
    except ContainmentError as exc:
        raise EditError(f"source: {exc}") from exc
    if not source or not target.is_file():
        raise EditError(f"source '{source}' is not a file under the root")
    return hashlib.sha256(target.read_bytes()).hexdigest()


def _template(root, ontology, kind):
    path = root / "_templates" / f"{kind}.md.tmpl"
    if path.is_file():
        return read_text_inside(path, root)
    return DEFAULT_TEMPLATE if ontology.object_types[kind]["implements"] else MINIMAL_TEMPLATE


def _group(line):
    names = set(PLACEHOLDER.findall(line))
    return next((group for group in REPEATING if names & group), None)


def _render(template, values):
    """Fill {{name}}; the lines holding a repeating placeholder run once per value of that field."""
    lines, out, index = template.splitlines(keepends=True), [], 0
    while index < len(lines):
        group = _group(lines[index])
        stop = index + 1
        while group is not None and stop < len(lines) and _group(lines[stop]) == group:
            stop += 1
        block = lines[index:stop]
        if group is None:
            out.extend(_fill(line, values) for line in block)
        else:
            missing = sorted(group - set(values))
            if missing:
                raise EditError(f"template placeholder {{{{{missing[0]}}}}} has no value")
            for number in range(len(values[sorted(group)[0]])):
                scalar = {**values, **{name: values[name][number] for name in group}}
                out.extend(_fill(line, scalar) for line in block)
        index = stop
    return "".join(out)


def _fill(line, values):
    def fill(match):
        if match.group(1) not in values:
            raise EditError(f"template placeholder {{{{{match.group(1)}}}}} has no value")
        return json.dumps(str(values[match.group(1)]), ensure_ascii=False)[1:-1]
    return PLACEHOLDER.sub(fill, line)
