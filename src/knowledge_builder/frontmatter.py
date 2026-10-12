"""Subset frontmatter parser: scalars, lists, and lists of maps. No PyYAML."""

import json


class FrontmatterError(ValueError):
    """The document frontmatter is not in the supported subset."""


def split_frontmatter(text):
    if text.startswith("\ufeff"):
        text = text[1:]
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise FrontmatterError("missing opening frontmatter fence")
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return lines[1:index]
    raise FrontmatterError("missing closing frontmatter fence")


def parse_frontmatter(text):
    lines = split_frontmatter(text)
    mapping, index = _parse_map(lines, 0, 0)
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index < len(lines):
        raise FrontmatterError(f"unparsed frontmatter: {lines[index].strip()}")
    return mapping


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def _next_content(lines, index):
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines):
        return None
    return index


def _parse_scalar(raw):
    raw = raw.strip()
    if raw == "":
        raise FrontmatterError("empty scalar")
    if raw.startswith('"'):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise FrontmatterError(f"bad quoted scalar: {raw}") from exc
        if not isinstance(value, str):
            raise FrontmatterError(f"expected string scalar: {raw}")
        return value
    if raw.startswith("'"):
        if len(raw) < 2 or not raw.endswith("'"):
            raise FrontmatterError(f"bad quoted scalar: {raw}")
        return raw[1:-1].replace("''", "'")
    if raw.startswith("["):
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise FrontmatterError(f"bad list scalar: {raw}") from exc
    return raw


def _is_map_item(rest):
    if rest.startswith(('"', "'", "[")):
        return False
    key, sep, _value = rest.partition(":")
    return sep == ":" and bool(key.strip()) and " " not in key.strip()


def _parse_map(lines, index, indent):
    mapping = {}
    while index < len(lines):
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("#"):
            index += 1
            continue
        current = _indent(line)
        if current < indent:
            break
        if current != indent:
            raise FrontmatterError(f"unexpected indent: {line.strip()}")
        stripped = line.strip()
        if stripped.startswith("- "):
            break
        key, sep, rest = stripped.partition(":")
        key = key.strip()
        if sep != ":" or not key or any(char.isspace() for char in key):
            raise FrontmatterError(f"bad key: {stripped}")
        rest = rest.strip()
        if rest == "":
            nxt = _next_content(lines, index + 1)
            if nxt is None or _indent(lines[nxt]) <= indent:
                mapping[key] = None
                index += 1
                continue
            if lines[nxt].strip().startswith("- "):
                mapping[key], index = _parse_list(lines, nxt, _indent(lines[nxt]))
            else:
                mapping[key], index = _parse_map(lines, nxt, _indent(lines[nxt]))
        else:
            mapping[key] = _parse_scalar(rest)
            index += 1
    return mapping, index


def _parse_list(lines, index, indent):
    items = []
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        current = _indent(line)
        if current < indent:
            break
        if current != indent:
            raise FrontmatterError(f"unexpected indent: {line.strip()}")
        stripped = line.strip()
        if not stripped.startswith("- "):
            break
        rest = stripped[2:].strip()
        if rest == "":
            raise FrontmatterError("empty list item")
        if _is_map_item(rest):
            key, _sep, value = rest.partition(":")
            item = {}
            item[key.strip()] = _parse_scalar(value.strip()) if value.strip() else None
            index += 1
            while index < len(lines):
                cont = lines[index]
                if not cont.strip():
                    index += 1
                    continue
                if _indent(cont) <= indent or cont.strip().startswith("- "):
                    break
                piece = cont.strip()
                cont_key, cont_sep, cont_value = piece.partition(":")
                if cont_sep != ":" or not cont_key.strip():
                    raise FrontmatterError(f"bad key: {piece}")
                item[cont_key.strip()] = _parse_scalar(cont_value.strip()) if cont_value.strip() else None
                index += 1
            items.append(item)
        else:
            items.append(_parse_scalar(rest))
            index += 1
    return items, index
