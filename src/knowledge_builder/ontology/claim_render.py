"""Render claim and source files from the root's `_templates/` (packaged defaults when the root has none)."""

import json
import re

from knowledge_builder.containment import read_text_inside
from knowledge_builder.ontology.template_files import TemplateError, packaged_template

TOKEN = re.compile(r"\{\{(!?)(\w+)\}\}")


def render(template, scalars, raw):
    """`{{x}}` is a JSON-escaped scalar to sit inside quotes; `{{!x}}` is inserted as given."""
    def fill(match):
        table = raw if match.group(1) else scalars
        if match.group(2) not in table:
            raise ValueError(f"template placeholder {match.group(0)} has no value")
        value = str(table[match.group(2)])
        return value if match.group(1) else json.dumps(value, ensure_ascii=False)[1:-1]
    return TOKEN.sub(fill, template)


def template_for(root, kind):
    path = root / "_templates" / f"{kind}.md.tmpl"
    try:
        return read_text_inside(path, root) if path.is_file() else packaged_template(kind)
    except (OSError, TemplateError) as exc:
        raise ValueError(f"no template for '{kind}': {exc}") from exc


def evidence_rows(entry):
    names = ("atom", "run", "source", "evidence_uri", "quote")
    return "\n".join(f"{'  - ' if i == 0 else '    '}{n}: {json.dumps(entry[n], ensure_ascii=False)}" for i, n in enumerate(names))


def capture_rows(capture):
    names = ("evidence_uri", "sha256", "fetched")
    return "\n".join(f"{'  - ' if i == 0 else '    '}{n}: {json.dumps(capture[n], ensure_ascii=False)}" for i, n in enumerate(names))
