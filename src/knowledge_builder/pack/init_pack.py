"""pack init: scaffold a root from the packaged starter and open its research run."""

import json
import re
import shutil
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from knowledge_builder.ontology.template_files import (
    TEMPLATE_SUBDIR, packaged_template_file, starter_ontology, template_names,
)

PACK_FILE = "pack.json"


class PackError(ValueError):
    """The pack command cannot run; the message names the next action."""


def default_run(topic):
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-") or "pack"
    return f"{slug}-{date.today().strftime('%y%m%d')}"


def init_pack(root, topic, run=None, budget=400, require=(), researcher=None):
    """Create root (or fill an existing empty one). A failure removes what this call created."""
    from knowledge_builder.research.run_driver import cmd_run_init

    root = Path(root).expanduser()
    if not topic.strip():
        raise PackError("--topic must not be empty")
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise PackError(f"root is not empty: {root} (pack init only scaffolds a new or empty directory)")
    run = run or default_run(topic)
    created_root = not root.exists()
    root.mkdir(parents=True, exist_ok=True)
    try:
        (root / "ontology.yaml").write_text(starter_ontology(), encoding="utf-8")
        (root / TEMPLATE_SUBDIR).mkdir()
        for file_name in template_names():
            (root / TEMPLATE_SUBDIR / file_name).write_text(packaged_template_file(file_name), encoding="utf-8")
        (root / "claims").mkdir()
        (root / "sources").mkdir()
        (root / PACK_FILE).write_text(json.dumps({"topic": topic, "run": run}, indent=2) + "\n", encoding="utf-8")
        cmd_run_init(SimpleNamespace(root=str(root), id=run, budget=budget, require=list(require) or None, researcher=researcher))
    except BaseException as exc:
        _undo(root, created_root)
        if isinstance(exc, SystemExit):
            raise PackError(f"run init rejected the run id or arguments: {run!r}") from None
        raise
    return run


def _undo(root, created_root):
    if created_root:
        shutil.rmtree(root, ignore_errors=True)
        return
    for child in root.iterdir():
        shutil.rmtree(child, ignore_errors=True) if child.is_dir() else child.unlink(missing_ok=True)


def read_pack(root):
    """{"topic", "run"} from pack.json, or {} when the root has none."""
    path = Path(root) / PACK_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}
