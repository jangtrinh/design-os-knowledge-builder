"""Structural verify for an external knowledge root. No network, no PyYAML."""

import hashlib
import re
import sys
from pathlib import Path

from knowledge_builder.anchors import heading_present, parse_attributes, visible_lines
from knowledge_builder.anchors import AnchorSyntaxError
from knowledge_builder.containment import ContainmentError, require_inside
from knowledge_builder.frontmatter import FrontmatterError, parse_frontmatter
from knowledge_builder.quote_check import file_contains_quote, normalise_newlines


HEADINGS = (
    "## Purpose",
    "## When to Use / When NOT",
    "## Core Knowledge Content",
    "## Failure Modes",
)
TIERS = {"verified", "community_reference", "draft"}
KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")
ANCHOR = re.compile(r"<!--\s*ease:source\b(.*?)-->", re.DOTALL)
OPEN_ANCHOR = re.compile(r"<!--\s*ease:source\b")


def cmd_verify(args):
    files, anchors, messages = verify_root(args.root, claims=bool(getattr(args, "claims", False)))
    print(f"files: {files}")
    print(f"anchors: {anchors}")
    print(f"failures: {len(messages)}")
    for message in messages:
        print(message)
    if messages:
        sys.exit(1)


def verify_root(root, claims=False):
    """Return (files, anchors, failure messages). claims=True also checks anchor quotes."""
    root = Path(root)
    if not root.is_dir():
        return 0, 0, [f"{root}: not a directory"]
    root = root.resolve()
    files = 0
    anchors = 0
    failures = []
    found, walk_errors = _markdown_files(root)
    failures.extend(walk_errors)
    for path in found:
        files += 1
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            failures.append(f"{rel}: {exc}")
            continue
        parsed_anchors = _anchors(text)
        anchors += sum(1 for item in parsed_anchors if item is not None)
        if len(OPEN_ANCHOR.findall(text)) != len(parsed_anchors) or any(
            item is None for item in parsed_anchors
        ):
            failures.append(f"{rel}: malformed ease:source anchor")
        try:
            data = parse_frontmatter(text)
        except FrontmatterError as exc:
            failures.append(f"{rel}: {exc}")
            data = None
        if data is not None:
            _check_metadata(data, rel, failures)
            _check_sources(root, rel, data.get("source_attribution"), failures)
        _check_headings(text, rel, failures)
        checked = 0
        quotes = []
        for index, attrs in enumerate(parsed_anchors):
            if attrs is None:
                continue
            where = f"anchor[{index}]"
            _check_ref(root, rel, attrs.get("uri"), attrs.get("sha256"), failures, where)
            if isinstance(attrs.get("quote"), str):
                quotes.append(attrs["quote"])
            if claims and _check_anchor_quote(root, rel, attrs, failures, where):
                checked += 1
        if claims and _has_uncited_core(text, quotes):
            failures.append(f"{rel}: uncited Core Knowledge content")
        if claims and checked == 0:
            failures.append(f"{rel}: no claim was checked")
    return files, anchors, failures


def _markdown_files(root):
    """Markdown under root. A symlink whose real path escapes root is an error."""
    found = []
    errors = []
    for path in root.rglob("*"):
        if path.suffix.lower() != ".md":
            continue
        relative = path.relative_to(root)
        if "_evidence" in relative.parts or path.name.lower() == "readme.md":
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
    return sorted(found), errors


def _anchors(text):
    found = []
    for match in ANCHOR.finditer(text):
        try:
            found.append(parse_attributes(match.group(1)))
        except AnchorSyntaxError:
            found.append(None)
    return found


def _check_metadata(data, rel, failures):
    if not isinstance(data, dict):
        failures.append(f"{rel}: frontmatter must be a mapping")
        return
    for key in ("id", "title", "domain", "description", "when", "trust_tier", "version"):
        if key not in data or data[key] is None:
            failures.append(f"{rel}: missing {key}")
    ident = data.get("id")
    if "id" in data and data["id"] is not None and not isinstance(ident, str):
        failures.append(f"{rel}: id must be a string")
    elif isinstance(ident, str) and KEBAB.fullmatch(ident) is None:
        failures.append(f"{rel}: id must be kebab-case")
    for key in ("title", "domain", "description", "version"):
        value = data.get(key)
        if key in data and data[key] is not None and (not isinstance(value, str) or not value.strip()):
            failures.append(f"{rel}: {key} must be a non-empty string")
    tier = data.get("trust_tier")
    if "trust_tier" in data and data["trust_tier"] is not None and not isinstance(tier, str):
        failures.append(f"{rel}: trust_tier must be a string")
    elif isinstance(tier, str) and tier not in TIERS:
        failures.append(f"{rel}: trust_tier must be verified, community_reference, or draft")
    when = data.get("when")
    if "when" in data and (
        not isinstance(when, list)
        or not when
        or any(not isinstance(item, str) or not item.strip() for item in when)
    ):
        failures.append(f"{rel}: when must be a non-empty list")


def _check_sources(root, rel, sources, failures):
    if not isinstance(sources, list) or not sources:
        failures.append(f"{rel}: source_attribution must be a non-empty list of {{uri, sha256}}")
        return
    for index, item in enumerate(sources):
        if not isinstance(item, dict):
            failures.append(f"{rel}: source_attribution[{index}] must be a mapping")
            continue
        _check_ref(root, rel, item.get("uri"), item.get("sha256"), failures, f"source_attribution[{index}]")


def _check_anchor_quote(root, rel, attrs, failures, where):
    """True only when the anchor quote occurs in the hashed file."""
    quote = attrs.get("quote")
    if not isinstance(quote, str) or quote.strip() == "":
        failures.append(f"{rel}: {where} UNCHECKED")
        return False
    target, error = _locate(root, attrs.get("uri"))
    if error or target is None or not target.is_file() or not file_contains_quote(target, quote):
        failures.append(f"{rel}: {where} quote is not in the hashed file")
        return False
    return True


def _check_headings(text, rel, failures):
    lines = visible_lines(text)
    for heading in HEADINGS:
        if not heading_present(lines, heading):
            failures.append(f"{rel}: missing heading {heading}")


def _has_uncited_core(text, quotes):
    """True when Core Knowledge prose remains after declared quotes are removed."""
    core = normalise_newlines(_core_section(text))
    for quote in quotes:
        core = core.replace(normalise_newlines(quote), "")
    return core.strip() != ""


def _core_section(text):
    lines = visible_lines(text)
    start = None
    for index, line in enumerate(lines):
        if heading_present([line], "## Core Knowledge Content"):
            start = index + 1
            break
    if start is None:
        return ""
    end = len(lines)
    for index in range(start, len(lines)):
        stripped = lines[index].strip()
        if stripped == "##" or stripped.startswith("## "):
            end = index
            break
    return "\n".join(lines[start:end])


def _check_ref(root, rel, uri, sha, failures, where):
    target, error = _locate(root, uri)
    if error:
        failures.append(f"{rel}: {where} {error}")
        return
    if not isinstance(sha, str) or HEX64.fullmatch(sha) is None:
        failures.append(f"{rel}: {where} sha256 is not 64 hex for {uri}")
        return
    if not target.is_file():
        failures.append(f"{rel}: {where} missing file {uri}")
        return
    actual = _sha256(target)
    if actual.lower() != sha.lower():
        failures.append(f"{rel}: {where} sha256 mismatch for {uri}")


def _locate(root, uri):
    if not isinstance(uri, str) or not uri.strip():
        return None, "uri is missing"
    uri = uri.strip()
    if uri.lower().startswith("file:"):
        return None, f"uri is not repo-relative: {uri}"
    if _is_absolute(uri):
        return None, f"uri is not repo-relative: {uri}"
    candidate = root / uri
    try:
        require_inside(candidate, root)
    except ContainmentError as exc:
        if str(exc).startswith("unreadable"):
            return None, f"unreadable: {uri}"
        return None, f"uri escapes root: {uri}"
    return candidate, None


def _is_absolute(uri):
    if uri.startswith(("/", "\\")) or Path(uri).is_absolute():
        return True
    return len(uri) >= 3 and uri[0].isalpha() and uri[1] == ":" and uri[2] in "/\\"


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
