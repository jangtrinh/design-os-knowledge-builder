"""Machine-readable index of an external knowledge root. No network."""

import fnmatch
import hashlib
import json
import sys
from pathlib import Path

from knowledge_builder.frontmatter import FrontmatterError, parse_frontmatter


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

    entries = []
    errors = []
    for path in _markdown_files(root, _exclude_patterns(args)):
        entry, error = _entry(path, root)
        if error:
            errors.append(error)
        else:
            entries.append(entry)
    if errors:
        for error in errors:
            print(f"[-] {error}", file=sys.stderr)
        sys.exit(1)

    out_file = root / "index.json"
    with open(out_file, "w", encoding="utf-8") as handle:
        json.dump(entries, handle, indent=2)
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
    found = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() != ".md":
            continue
        if path.name.lower() == "readme.md":
            continue
        relative = path.relative_to(root)
        if _is_excluded(relative, patterns):
            continue
        found.append(path)
    return sorted(found, key=lambda item: item.relative_to(root).as_posix())


def _entry(path, root):
    rel = path.relative_to(root).as_posix()
    try:
        data = parse_frontmatter(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, FrontmatterError) as exc:
        return None, f"{rel}: {exc}"
    doc_id = data.get("id") if isinstance(data, dict) else None
    if not isinstance(doc_id, str) or not doc_id:
        return None, f"{rel}: frontmatter id is missing"
    if doc_id != path.stem:
        return None, f"{rel}: id {doc_id!r} does not match filename {path.name}"
    return {"id": doc_id, "path": rel, "sha256": _sha256(path)}, None


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


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
