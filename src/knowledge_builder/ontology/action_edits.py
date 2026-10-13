"""Text-level frontmatter edits. Only the touched lines change; the rest stays byte-identical."""

import json
import re

FORBIDDEN_SET_KEYS = {"id", "link_types", "source_attribution", "when"}
_KEY_LINE = re.compile(r"^([A-Za-z0-9_-]+):(.*)$")


class EditError(ValueError):
    """An edit cannot be applied safely."""


def set_key(text, key, value):
    if key in FORBIDDEN_SET_KEYS:
        raise EditError(f"set cannot change structured or identity key '{key}'")
    lines, close = _frontmatter(text)
    new = f"{key}: {json.dumps(value, ensure_ascii=False)}{_eol(lines)}"
    start = _find_key(lines, close, key)
    if start is None:
        return "".join(lines[:close] + [new] + lines[close:])
    if _block_end(lines, start, close) != start + 1 or not _KEY_LINE.match(lines[start]).group(2).strip():
        raise EditError(f"key '{key}' is not a single-line scalar")
    return "".join(lines[:start] + [new] + lines[start + 1 :])


def add_link(text, link_type, target_id):
    lines, close = _frontmatter(text)
    eol = _eol(lines)
    item = [f"  - link_type: {json.dumps(link_type)}{eol}", f"    target_id: {json.dumps(target_id)}{eol}"]
    start = _find_key(lines, close, "link_types")
    if start is None:
        return "".join(lines[:close] + [f"link_types:{eol}"] + item + lines[close:])
    if _links(lines, start, close) and (link_type, target_id) in [pair for pair, _a, _b in _links(lines, start, close)]:
        raise EditError(f"link {link_type} -> {target_id} already exists")
    rest = _KEY_LINE.match(lines[start]).group(2).strip()
    if rest == "[]":
        return "".join(lines[:start] + [f"link_types:{eol}"] + item + lines[start + 1 :])
    if rest:
        raise EditError("link_types is not a block list")
    end = _block_end(lines, start, close)
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    return "".join(lines[:end] + item + lines[end:])


def remove_link(text, link_type, target_id):
    lines, close = _frontmatter(text)
    start = _find_key(lines, close, "link_types")
    found = [(a, b) for pair, a, b in _links(lines, start, close) if pair == (link_type, target_id)] if start is not None else []
    if not found:
        raise EditError(f"link {link_type} -> {target_id} does not exist")
    first, last = found[0]
    remaining = [pair for pair, _a, _b in _links(lines, start, close)]
    if len(remaining) == 1:
        first, last = start, _block_end(lines, start, close)
    return "".join(lines[:first] + lines[last:])


def _frontmatter(text):
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise EditError("document has no frontmatter")
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return lines, index
    raise EditError("frontmatter is not closed")


def _eol(lines):
    return "\r\n" if lines[0].endswith("\r\n") else "\n"


def _find_key(lines, close, key):
    found = [
        index for index in range(1, close)
        if (match := _KEY_LINE.match(lines[index].rstrip("\r\n"))) and match.group(1) == key
    ]
    if len(found) > 1:
        raise EditError(f"frontmatter has duplicate key '{key}'; fix it before editing")
    return found[0] if found else None


def _block_end(lines, start, close):
    """Index after the key line and its indented children."""
    index = start + 1
    while index < close and (not lines[index].strip() or lines[index][0] == " "):
        index += 1
    return index


def _links(lines, start, close):
    """[((link_type, target_id), first_line, after_last_line)] for the block list under link_types."""
    found, end, index = [], _block_end(lines, start, close), start + 1
    while index < end:
        if lines[index].lstrip().startswith("- "):
            stop = index + 1
            while stop < end and not lines[stop].lstrip().startswith("- "):
                stop += 1
            fields = {}
            for row in lines[index:stop]:
                match = re.match(r"^\s*(?:- )?(link_type|target_id):\s*(.*?)\s*$", row)
                if match:
                    fields[match.group(1)] = match.group(2).strip("\"'")
            found.append(((fields.get("link_type"), fields.get("target_id")), index, stop))
            index = stop
        else:
            index += 1
    return found
