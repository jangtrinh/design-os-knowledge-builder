"""Structural verify for an external knowledge root. No network, no PyYAML."""

import hashlib
import re
import sys
from pathlib import Path

from knowledge_builder.frontmatter import FrontmatterError, parse_frontmatter
from knowledge_builder.quote_check import file_contains_quote


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
ATTR = re.compile(r"""([A-Za-z_][A-Za-z0-9_]*)=(?:"([^"]*)"|'([^']*)'|(\S+))""")
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
    for path in _markdown_files(root):
        files += 1
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            failures.append(f"{rel}: {exc}")
            continue
        parsed_anchors = _anchors(text)
        anchors += len(parsed_anchors)
        if len(OPEN_ANCHOR.findall(text)) != len(parsed_anchors):
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
        for index, attrs in enumerate(parsed_anchors):
            where = f"anchor[{index}]"
            _check_ref(root, rel, attrs.get("uri"), attrs.get("sha256"), failures, where)
            if claims:
                _check_anchor_quote(root, rel, attrs, failures, where)
    return files, anchors, failures


def _markdown_files(root):
    found = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() != ".md":
            continue
        rel = path.relative_to(root)
        if "_evidence" in rel.parts or path.name.lower() == "readme.md":
            continue
        found.append(path)
    return sorted(found)


def _anchors(text):
    found = []
    for match in ANCHOR.finditer(text):
        attrs = {}
        for attr in ATTR.finditer(match.group(1)):
            value = attr.group(2)
            if value is None:
                value = attr.group(3)
            if value is None:
                value = attr.group(4)
            attrs[attr.group(1)] = value
        found.append(attrs)
    return found


def _check_metadata(data, rel, failures):
    if not isinstance(data, dict):
        failures.append(f"{rel}: frontmatter must be a mapping")
        return
    for key in ("id", "title", "domain", "description", "when", "trust_tier", "version"):
        if key not in data or data[key] is None:
            failures.append(f"{rel}: missing {key}")
    ident = data.get("id")
    if isinstance(ident, str) and KEBAB.fullmatch(ident) is None:
        failures.append(f"{rel}: id must be kebab-case")
    for key in ("title", "domain", "description", "version"):
        value = data.get(key)
        if key in data and data[key] is not None and (not isinstance(value, str) or not value.strip()):
            failures.append(f"{rel}: {key} must be a non-empty string")
    tier = data.get("trust_tier")
    if isinstance(tier, str) and tier not in TIERS:
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
    quote = attrs.get("quote")
    if not isinstance(quote, str) or quote.strip() == "":
        failures.append(f"{rel}: {where} UNCHECKED")
        return
    target, error = _locate(root, attrs.get("uri"))
    if error or target is None or not target.is_file() or not file_contains_quote(target, quote):
        failures.append(f"{rel}: {where} quote is not in the hashed file")


def _check_headings(text, rel, failures):
    for heading in HEADINGS:
        if heading not in text:
            failures.append(f"{rel}: missing heading {heading}")


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
    candidate = (root / uri).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
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
