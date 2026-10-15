"""pack migrate: read-only scan of a UKMC.v1 root. Nothing here writes."""

import hashlib
import json
import re
from pathlib import Path

from knowledge_builder.anchors import AnchorSyntaxError, parse_attributes
from knowledge_builder.frontmatter import FrontmatterError, parse_frontmatter
from knowledge_builder.ontology.claim_atoms import header_field
from knowledge_builder.pack.init_pack import PackError

ANCHOR = re.compile(r"<!--\s*ease:source\b(.*?)-->", re.DOTALL)
_HEADING = re.compile(r"^## .*$", re.MULTILINE)
_LIST_ITEM = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
_COMMENT = re.compile(r"<!--.*?-->")
KNOWN_KEYS = {"id", "title", "domain", "description", "when", "source_attribution", "trust_tier", "version", "object_type"}


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def split_document(text):
    """(frontmatter text including both fences, body). The body starts right after the closing fence line."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise PackError("document has no frontmatter")
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "".join(lines[: index + 1]), "".join(lines[index + 1 :])
    raise PackError("frontmatter is not closed")


def read_runs(root):
    """{run: {"atoms": [dict], "state": dict, "ledger_sha256", "state_sha256"}} for every _evidence/<run>."""
    runs, evidence = {}, Path(root) / "_evidence"
    for run_dir in sorted(evidence.iterdir()) if evidence.is_dir() else []:
        if run_dir.is_symlink():
            raise PackError(f"{run_dir}: a symlinked run directory is not migrated")
        ledger, state = run_dir / "evidence.jsonl", run_dir / "state.json"
        if not run_dir.is_dir() or not (ledger.is_file() or (run_dir / "sources").is_dir()):
            continue
        atoms = []
        for number, line in enumerate(ledger.read_text(encoding="utf-8").splitlines() if ledger.is_file() else [], start=1):
            if not line.strip():
                continue
            try:
                atom = json.loads(line)
            except ValueError as exc:
                raise PackError(f"{ledger}:{number}: not JSON: {exc}") from exc
            if not isinstance(atom, dict) or not isinstance(atom.get("id"), str):
                raise PackError(f"{ledger}:{number}: an atom needs a string id")
            atoms.append(atom)
        parsed = _json_object(state)
        runs[run_dir.name] = {
            "atoms": atoms, "state": parsed,
            "ledger_sha256": sha256_of(ledger) if ledger.is_file() else None,
            "state_sha256": sha256_of(state) if state.is_file() else None,
        }
    return runs


def _json_object(path):
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise PackError(f"{path}: not JSON: {exc}") from exc
    return data if isinstance(data, dict) else {}


def read_captures(root, runs, atoms_by_uri):
    """{legacy uri: {"path", "sha256", "run", "rel", "url", "fetched"}} for every file under _evidence/<run>/sources."""
    captures = {}
    for run in runs:
        base = Path(root) / "_evidence" / run / "sources"
        for path in sorted(base.rglob("*")) if base.is_dir() else []:
            if path.is_symlink():
                raise PackError(f"{path}: a symlink is not migrated")
            if not path.is_file():
                continue
            rel = path.relative_to(base).as_posix()
            uri = f"_evidence/{run}/sources/{rel}"
            atom_urls = [(a.get("metadata") or {}).get("url") for a in atoms_by_uri.get(uri, [])]
            url = next((u.strip() for u in atom_urls if isinstance(u, str) and u.strip()), None) or header_field(path, "Source-URL")
            captures[uri] = {"path": path, "sha256": sha256_of(path), "run": run, "rel": rel, "url": url, "fetched": header_field(path, "Fetched")}
    return captures


def read_modules(root):
    """Every v1 module: id, path, sha256, frontmatter dict, body text."""
    from knowledge_builder.verify import _markdown_files

    root = Path(root).resolve()
    files, errors = _markdown_files(root)
    if errors:
        raise PackError("; ".join(errors))
    modules = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        try:
            front = parse_frontmatter(text)
            _fence, body = split_document(text)
        except (FrontmatterError, PackError) as exc:
            raise PackError(f"{path.name}: {exc}") from exc
        modules.append({"id": front.get("id"), "path": path.relative_to(root).as_posix(), "sha256": sha256_of(path), "front": front, "body": body})
    return modules


def module_anchors(module):
    """[{"uri", "quote", "heading", "above", "start", "end"}] for the ease:source anchors in the body, in order."""
    body, found = module["body"], []
    for match in ANCHOR.finditer(body):
        try:
            attrs = parse_attributes(match.group(1))
        except AnchorSyntaxError as exc:
            raise PackError(f"{module['path']}: malformed ease:source anchor: {exc}") from exc
        if not attrs.get("uri") or not attrs.get("quote"):
            raise PackError(f"{module['path']}: an ease:source anchor needs uri and quote")
        headings = _HEADING.findall(body[: match.start()])
        found.append({
            "uri": attrs["uri"], "quote": attrs["quote"], "start": match.start(), "end": match.end(),
            "heading": headings[-1] if headings else "", "above": text_above(body, match.start()),
        })
    return found


def text_above(body, start):
    """The block (one list item, or one paragraph) directly above position start, as one line; '' when it is a code fence."""
    got = []
    for line in reversed(body[:start].rstrip().splitlines()):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            break
        if stripped.startswith(("```", "~~~")):
            return ""
        got.append(stripped)
        if _LIST_ITEM.match(stripped):
            break
    text = " ".join(reversed(got))
    text = _COMMENT.sub("", _LIST_ITEM.sub("", text, count=1))
    return " ".join(text.split(" Remedy:")[0].split())
