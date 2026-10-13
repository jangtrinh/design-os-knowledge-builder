"""Packaged starter files: knowledge_builder/templates/ontology.starter.yaml and _templates/*.md.tmpl.

Read through importlib.resources, so they work from a checkout, an editable install and a wheel.
"""

from importlib.resources import files

STARTER_ONTOLOGY = "ontology.starter.yaml"
TEMPLATE_SUBDIR = "_templates"


class TemplateError(FileNotFoundError):
    """A packaged template is missing."""


def _base():
    return files("knowledge_builder") / "templates"


def starter_ontology():
    return _read(_base() / STARTER_ONTOLOGY)


def template_names():
    """File names under _templates/, sorted."""
    return sorted(item.name for item in (_base() / TEMPLATE_SUBDIR).iterdir() if item.name.endswith(".md.tmpl"))


def packaged_template(name):
    """Text of _templates/<name>.md.tmpl."""
    return _read(_base() / TEMPLATE_SUBDIR / f"{name}.md.tmpl")


def packaged_template_file(file_name):
    return _read(_base() / TEMPLATE_SUBDIR / file_name)


def _read(resource):
    try:
        return resource.read_text(encoding="utf-8")
    except OSError as exc:
        raise TemplateError(f"packaged template missing: {resource}") from exc
