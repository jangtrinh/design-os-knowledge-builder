"""Machine-readable index of an external knowledge root. No network."""

import fnmatch
import hashlib
import json
import sys
from pathlib import Path

from knowledge_builder.containment import (
    ContainmentError,
    atomic_write,
    read_bytes_inside,
    require_inside,
)
from knowledge_builder.frontmatter import FrontmatterError, parse_frontmatter
from knowledge_builder.ontology.index_enrich import enrich_entries
from knowledge_builder.ontology.schema import OntologyError
from knowledge_builder.ontology_mode import require_ontology


DEFAULT_EXCLUDE = "_evidence/**"


def cmd_index(args):
    root = Path(args.root).expanduser().resolve()
    package = package_directory().resolve()
    if _is_inside(root, package):
        print(f"[-] Refusing knowledge root inside the package: {root}", file=sys.stderr)
        sys.exit(2)
    if not root.is_dir():
        print(f"[-] Directory not found: {root}", file=sys.stderr)
        sys.exit(1)

    require_ontology(root, getattr(args, "legacy", False))
    entries = []
    found, errors = _markdown_files(root, _exclude_patterns(args))
    for path in found:
        entry, error = _entry(path, root)
        if error:
            errors.append(error)
        else:
            entries.append(entry)
    if errors:
        for error in errors:
            print(f"[-] {error}", file=sys.stderr)
        sys.exit(1)

    try:
        enrich_entries(root, entries)
    except OntologyError as exc:
        print(f"[-] {exc}", file=sys.stderr)
        sys.exit(1)

    out_file = root / "index.json"
    try:
        atomic_write(root, "index.json", json.dumps(entries, indent=2).encode("utf-8"))
    except ContainmentError as exc:
        print(f"[-] {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"[✓] Compiled machine-readable index with {len(entries)} file(s) into: {out_file}")


def package_directory():
    """Directory that contains this project's pyproject.toml."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    raise FileNotFoundError("pyproject.toml not found above knowledge_builder")


def _exclude_patterns(args):
    patterns = getattr(args, "exclude", None)
    if not patterns:
        return [DEFAULT_EXCLUDE]
    return [pattern for pattern in patterns if pattern and pattern.strip()]


def _markdown_files(root, patterns):
    """Markdown under root. A symlink whose real path escapes root is an error."""
    found = []
    errors = []
    for path in root.rglob("*"):
        if path.suffix.lower() != ".md":
            continue
        relative = path.relative_to(root)
        if path.name.lower() == "readme.md" or _is_excluded(relative, patterns):
            continue
        if path.is_dir() and not path.is_symlink():
            continue
        rel = relative.as_posix()
        try:
            require_inside(path, root)
        except ContainmentError as exc:
            errors.append(f"{rel}: {exc}")
            continue
        if not path.is_file():
            errors.append(f"{rel}: unreadable")
            continue
        found.append(path)
    found.sort(key=lambda item: item.relative_to(root).as_posix())
    return found, errors


def _entry(path, root):
    rel = path.relative_to(root).as_posix()
    try:
        blob = read_bytes_inside(path, root)
        data = parse_frontmatter(blob.decode("utf-8"))
    except (ContainmentError, OSError, UnicodeError, FrontmatterError) as exc:
        return None, f"{rel}: {exc}"
    doc_id = data.get("id") if isinstance(data, dict) else None
    if not isinstance(doc_id, str) or not doc_id:
        return None, f"{rel}: frontmatter id is missing"
    if doc_id != path.stem:
        return None, f"{rel}: id {doc_id!r} does not match filename {path.name}"
    return {"id": doc_id, "path": rel, "sha256": hashlib.sha256(blob).hexdigest()}, None


def _is_inside(root, package):
    try:
        root.relative_to(package)
    except ValueError:
        return False
    return True


def _is_excluded(relative, patterns):
    posix = relative.as_posix()
    return any(_glob_match(posix, pattern) for pattern in patterns)


def _glob_match(path, pattern):
    pattern = pattern.strip().replace("\\", "/").rstrip("/")
    if pattern.startswith("./"):
        pattern = pattern[2:]
    if not pattern:
        return False
    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/")
        if not prefix:
            return True
        return path == prefix or path.startswith(prefix + "/")
    return fnmatch.fnmatchcase(path, pattern)


