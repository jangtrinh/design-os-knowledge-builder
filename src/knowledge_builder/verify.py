"""Structural verify for an external knowledge root. No network, no PyYAML."""

import hashlib
import re
import sys
from pathlib import Path

from knowledge_builder.anchors import heading_present, parse_attributes, visible_lines
from knowledge_builder.anchors import AnchorSyntaxError
from knowledge_builder.containment import ContainmentError, require_inside
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
OPEN_ANCHOR = re.compile(r"<!--\s*ease:source\b")
# Not external facts. Same three labels as the anchor rule in the UKMC contract.
EXEMPT_LABELS = ("Derived:", "Lineup decision:", "Observed:")
_LIST_MARKER = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
_H3 = re.compile(r"^#{3,}(?:\s|$)")
_DELIM_CELL = re.compile(r":?-{3,}:?")


def cmd_verify(args):
    claims = bool(getattr(args, "claims", False))
    files, anchors, messages, exempt_blocks = verify_root(args.root, claims=claims)
    print(f"files: {files}")
    print(f"anchors: {anchors}")
    print(f"failures: {len(messages)}")
    if claims:
        print(f"exempt blocks: {exempt_blocks}")
    for message in messages:
        print(message)
    if messages:
        sys.exit(1)


def verify_root(root, claims=False):
    """Return (files, anchors, failure messages, exempt blocks).

    claims=True checks anchor quotes and per-block citations in Core Knowledge.
    """
    root = Path(root)
    if not root.is_dir():
        return 0, 0, [f"{root}: not a directory"], 0
    root = root.resolve()
    files = 0
    anchors = 0
    exempt_blocks = 0
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
        for index, attrs in enumerate(parsed_anchors):
            if attrs is None:
                continue
            where = f"anchor[{index}]"
            _check_ref(root, rel, attrs.get("uri"), attrs.get("sha256"), failures, where)
            if claims and _check_anchor_quote(root, rel, attrs, failures, where):
                checked += 1
        if claims:
            block_failures, exempt_here = _uncited_blocks(text, rel)
            failures.extend(block_failures)
            exempt_blocks += exempt_here
        if claims and checked == 0:
            failures.append(f"{rel}: no claim was checked")
    return files, anchors, failures, exempt_blocks


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


def _uncited_blocks(text, rel):
    """Failure lines for Core blocks with no ease:source, plus the exempt count."""
    records = _line_records(text)
    bounds = _core_bounds(records)
    if bounds is None:
        return [], 0
    start, end = bounds
    blocks = _blocks(records, start, end)
    spans = _anchor_spans(text)
    if end < len(records):
        limit = records[end][0]
    elif records:
        limit = records[-1][0] + 1
    else:
        limit = 1
    failures = []
    exempt = 0
    for index, (begin, finish, lines) in enumerate(blocks):
        if _is_exempt(lines):
            exempt += 1
            continue
        nxt = blocks[index + 1][0] if index + 1 < len(blocks) else limit
        if _is_cited(begin, finish, nxt, spans):
            continue
        failures.append(f"{rel}:{begin}: uncited block: {_preview(lines)}")
    return failures, exempt


def _line_records(text):
    """Original lines with comments removed, then fenced code marked."""
    records = []
    in_comment = False
    in_fence = False
    for number, line in enumerate(text.splitlines(), 1):
        shown, in_comment = _strip_comment(line, in_comment)
        if in_fence:
            if shown.startswith("```"):
                in_fence = False
                records.append((number, shown, "fence-close"))
            else:
                records.append((number, shown, "fence"))
            continue
        if shown.startswith("```"):
            in_fence = True
            records.append((number, shown, "fence-open"))
            continue
        records.append((number, shown, "blank" if shown == "" else "text"))
    return records


def _strip_comment(line, in_comment):
    visible = []
    index = 0
    while index < len(line):
        if in_comment:
            end = line.find("-->", index)
            if end < 0:
                return "".join(visible).strip(), True
            in_comment = False
            index = end + 3
            continue
        start = line.find("<!--", index)
        if start < 0:
            visible.append(line[index:])
            break
        visible.append(line[index:start])
        end = line.find("-->", start + 4)
        if end < 0:
            return "".join(visible).strip(), True
        index = end + 3
    return "".join(visible).strip(), in_comment


def _core_bounds(records):
    start = None
    for index, (_number, text, kind) in enumerate(records):
        if kind == "text" and heading_present([text], "## Core Knowledge Content"):
            start = index
            break
    if start is None:
        return None
    end = len(records)
    for index in range(start + 1, len(records)):
        _number, text, kind = records[index]
        if kind == "text" and (text == "##" or text.startswith("## ")):
            end = index
            break
    return start, end


def _blocks(records, start, end):
    blocks = []
    index = start + 1
    while index < end:
        _number, text, kind = records[index]
        if kind in ("blank", "fence-close"):
            index += 1
            continue
        if kind == "fence-open":
            index, block = _fence_block(records, index, end)
            blocks.append(block)
            continue
        if kind != "text" or _is_h3(text):
            index += 1
            continue
        if _starts_table(records, index, end):
            index, block = _table_block(records, index, end)
            blocks.append(block)
            continue
        index, block = _text_block(records, index, end)
        blocks.append(block)
    return blocks


def _fence_block(records, index, end):
    begin = records[index][0]
    lines = []
    index += 1
    while index < end and records[index][2] != "fence-close":
        if records[index][1]:
            lines.append(records[index][1])
        index += 1
    if index < end and records[index][2] == "fence-close":
        finish = records[index][0]
        index += 1
    else:
        finish = records[index - 1][0]
    return index, (begin, finish, lines)


def _table_block(records, index, end):
    begin = records[index][0]
    lines = []
    finish = begin
    while index < end and records[index][2] == "text" and "|" in records[index][1]:
        lines.append(records[index][1])
        finish = records[index][0]
        index += 1
    return index, (begin, finish, lines)


def _text_block(records, index, end):
    begin = records[index][0]
    lines = [records[index][1]]
    finish = begin
    index += 1
    while index < end and not _text_stops(records, index, end):
        lines.append(records[index][1])
        finish = records[index][0]
        index += 1
    return index, (begin, finish, lines)


def _text_stops(records, index, end):
    _number, text, kind = records[index]
    if kind != "text":
        return True
    return _is_h3(text) or _is_list_item(text) or _starts_table(records, index, end)


def _starts_table(records, index, end):
    if index + 1 >= end:
        return False
    _number, header, header_kind = records[index]
    _next, delim, delim_kind = records[index + 1]
    if header_kind != "text" or delim_kind != "text":
        return False
    return "|" in header and _is_delim(delim)


def _is_delim(text):
    cells = [cell.strip() for cell in text.strip().strip("|").split("|")]
    return bool(cells) and all(_DELIM_CELL.fullmatch(cell) for cell in cells)


def _is_h3(text):
    return _H3.match(text) is not None


def _is_list_item(text):
    return _LIST_MARKER.match(text) is not None


def _is_exempt(lines):
    if not lines:
        return False
    text = _LIST_MARKER.sub("", lines[0], count=1)
    return text.startswith(EXEMPT_LABELS)


def _is_cited(begin, finish, nxt, spans):
    for span_start, span_end in spans:
        if span_start <= finish and span_end >= begin:
            return True
        if finish < span_start < nxt:
            return True
    return False


def _anchor_spans(text):
    spans = []
    for match in ANCHOR.finditer(text):
        end = max(match.start(), match.end() - 1)
        spans.append((_lineno(text, match.start()), _lineno(text, end)))
    return spans


def _lineno(text, offset):
    return text.count("\n", 0, offset) + 1


def _preview(lines):
    return " ".join(line.strip() for line in lines if line.strip())[:60]


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
