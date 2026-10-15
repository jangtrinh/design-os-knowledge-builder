"""Shared helpers for build.py, validate.py and look.py: locate the product, run its CLI, read pack frontmatter.

Stdlib only. Never writes bytecode, never installs, never touches the network.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

SKILL_DIR = Path(__file__).resolve().parent
EXIT_OK, EXIT_REJECT, EXIT_CANNOT_RUN = 0, 1, 2


class CannotRun(Exception):
    """The product or its input is unavailable; callers print `runtime: could not run: ...` and exit 2."""


def product_src(repo_root=None):
    """The `src` directory holding knowledge_builder, or None when the package is already importable."""
    candidates = []
    if repo_root:
        candidates.append(Path(repo_root).expanduser().resolve())
    if os.environ.get("KNOWLEDGE_BUILDER_REPO"):
        candidates.append(Path(os.environ["KNOWLEDGE_BUILDER_REPO"]).expanduser().resolve())
    candidates.append(SKILL_DIR.parents[1])
    for repo in candidates:
        if (repo / "src" / "knowledge_builder" / "cli.py").is_file():
            return repo / "src"
    if repo_root:
        raise CannotRun(f"--repo-root {repo_root} has no src/knowledge_builder/cli.py")
    probe = subprocess.run([sys.executable, "-c", "import knowledge_builder.cli"], capture_output=True, text=True)
    if probe.returncode != 0:
        raise CannotRun("knowledge_builder is not importable: pass --repo-root <checkout> or pip install the package")
    return None


def run_cli(src, args, stdin=None):
    """Run `python -m knowledge_builder.cli <args>`; returns CompletedProcess (text mode)."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    if src is not None:
        env["PYTHONPATH"] = str(src) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "knowledge_builder.cli", *map(str, args)],
        input=stdin, capture_output=True, text=True, env=env, cwd=str(SKILL_DIR),
    )


def frontmatter(path):
    """(top-level scalars, link_types as [(link_type, target_id)]) of one markdown file; ({}, []) when none."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return {}, []
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not match:
        return {}, []
    scalars, links, kind = {}, [], None
    for line in match.group(1).splitlines():
        top = re.match(r'([A-Za-z_][\w-]*):\s*(.*)$', line)
        if top and not line.startswith(" "):
            scalars[top.group(1)] = top.group(2).strip().strip('"')
            continue
        item = re.match(r'\s+-?\s*link_type:\s*"?([^"]+)"?\s*$', line)
        if item:
            kind = item.group(1)
            continue
        target = re.match(r'\s+target_id:\s*"?([^"]+)"?\s*$', line)
        if target and kind:
            links.append((kind, target.group(1)))
    return scalars, links


def pack_objects(root):
    """Every markdown object of a pack: {id: (path, scalars, links)}; skips _templates, _evidence and dot dirs."""
    found = {}
    for path in sorted(Path(root).rglob("*.md")):
        parts = path.relative_to(root).parts
        if any(part.startswith(("_", ".")) for part in parts):
            continue
        scalars, links = frontmatter(path)
        if scalars.get("id"):
            found[scalars["id"]] = (path, scalars, links)
    return found
