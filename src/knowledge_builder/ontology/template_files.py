"""Packaged starter files: templates/ontology.starter.yaml and templates/_templates/*.md.tmpl.

They sit beside pyproject.toml, so they are found in a source checkout or an editable install.
"""

from pathlib import Path

STARTER_ONTOLOGY = "ontology.starter.yaml"
TEMPLATE_SUBDIR = "_templates"


class TemplateError(FileNotFoundError):
    """The packaged templates directory cannot be found."""


def templates_dir():
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "templates"
        if (parent / "pyproject.toml").is_file() and (candidate / STARTER_ONTOLOGY).is_file():
            return candidate
    raise TemplateError("templates/ontology.starter.yaml not found beside pyproject.toml; install with `pip install -e .` from the repository")


def packaged_template(name):
    """Text of templates/_templates/<name>.md.tmpl."""
    return (templates_dir() / TEMPLATE_SUBDIR / f"{name}.md.tmpl").read_text(encoding="utf-8")
