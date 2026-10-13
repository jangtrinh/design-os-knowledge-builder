"""Small YAML subset for ontology.yaml: block maps/lists plus flow `[..]` and `{..}`.

Scalars stay strings except quoted forms; the schema loader coerces bool/int.
Anything outside the subset raises SchemaSyntaxError with the line number.
"""

from knowledge_builder.ontology.schema_flow import SchemaSyntaxError, parse_inline


def parse_schema_yaml(text):
    rows = []
    for number, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise SchemaSyntaxError(f"line {number}: tab indentation")
        rows.append([len(raw) - len(raw.lstrip(" ")), stripped, number])
    if not rows:
        return {}
    value, index = _block(rows, 0, rows[0][0])
    if index < len(rows):
        raise SchemaSyntaxError(f"line {rows[index][2]}: unexpected indent")
    return value


def _block(rows, index, indent):
    if _is_item(rows[index][1]):
        return _list(rows, index, indent)
    return _map(rows, index, indent)


def _map(rows, index, indent):
    result = {}
    while index < len(rows) and rows[index][0] == indent and not _is_item(rows[index][1]):
        _indent, text, number = rows[index]
        key, rest = _split_key(text, number)
        if key in result:
            raise SchemaSyntaxError(f"line {number}: duplicate key {key}")
        index += 1
        if rest:
            result[key] = parse_inline(rest, number)
        elif index < len(rows) and rows[index][0] > indent:
            result[key], index = _block(rows, index, rows[index][0])
        else:
            result[key] = None
    _reject_stray(rows, index, indent)
    return result, index


def _list(rows, index, indent):
    items = []
    while index < len(rows) and rows[index][0] == indent and _is_item(rows[index][1]):
        _indent, text, number = rows[index]
        rest = text[1:].strip()
        if not rest:
            raise SchemaSyntaxError(f"line {number}: empty list item")
        if _looks_like_pair(rest):
            rows[index] = [indent + 2, rest, number]
            item, index = _map(rows, index, indent + 2)
            items.append(item)
        else:
            items.append(parse_inline(rest, number))
            index += 1
    _reject_stray(rows, index, indent)
    return items, index


def _is_item(text):
    return text == "-" or text.startswith("- ")


def _reject_stray(rows, index, indent):
    if index < len(rows) and rows[index][0] > indent:
        raise SchemaSyntaxError(f"line {rows[index][2]}: unexpected indent")


def _looks_like_pair(rest):
    if rest[0] in "[{\"'":
        return False
    return _find_colon(rest) is not None


def _find_colon(text):
    for position, char in enumerate(text):
        if char == ":" and (position + 1 == len(text) or text[position + 1] == " "):
            return position
    return None


def _split_key(text, number):
    position = _find_colon(text)
    key = text[:position].strip() if position is not None else ""
    if not key or any(char in key for char in "[]{}\"'"):
        raise SchemaSyntaxError(f"line {number}: bad key: {text}")
    return key, text[position + 1 :].strip()
