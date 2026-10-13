"""Small YAML subset for ontology.yaml: block maps/lists plus flow `[..]` and `{..}`.

Scalars stay strings except quoted forms; the schema loader coerces bool/int.
Anything outside the subset raises SchemaSyntaxError with the line number.
"""

import json


class SchemaSyntaxError(ValueError):
    """ontology.yaml uses syntax outside the supported subset."""


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
    if rows[index][1].startswith("- ") or rows[index][1] == "-":
        return _list(rows, index, indent)
    return _map(rows, index, indent)


def _map(rows, index, indent):
    result = {}
    while index < len(rows) and rows[index][0] == indent and not rows[index][1].startswith("- "):
        _indent, text, number = rows[index]
        key, rest = _split_key(text, number)
        if key in result:
            raise SchemaSyntaxError(f"line {number}: duplicate key {key}")
        index += 1
        if rest:
            result[key] = _inline(rest, number)
        elif index < len(rows) and rows[index][0] > indent:
            result[key], index = _block(rows, index, rows[index][0])
        else:
            result[key] = None
    _reject_stray(rows, index, indent)
    return result, index


def _list(rows, index, indent):
    items = []
    while index < len(rows) and rows[index][0] == indent and rows[index][1].startswith("-"):
        _indent, text, number = rows[index]
        rest = text[1:].strip()
        if not rest:
            raise SchemaSyntaxError(f"line {number}: empty list item")
        if _looks_like_pair(rest):
            rows[index] = [indent + 2, rest, number]
            item, index = _map(rows, index, indent + 2)
            items.append(item)
        else:
            items.append(_inline(rest, number))
            index += 1
    _reject_stray(rows, index, indent)
    return items, index


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


def _inline(text, number):
    parser = _Flow(text, number)
    value = parser.value()
    parser.finish()
    return value


class _Flow:
    def __init__(self, text, number):
        self.text, self.number, self.pos = text, number, 0

    def _fail(self, message):
        raise SchemaSyntaxError(f"line {self.number}: {message}: {self.text}")

    def _skip(self):
        while self.pos < len(self.text) and self.text[self.pos] == " ":
            self.pos += 1

    def finish(self):
        self._skip()
        if self.pos != len(self.text):
            self._fail("trailing text")

    def value(self):
        self._skip()
        if self.pos >= len(self.text):
            self._fail("missing value")
        char = self.text[self.pos]
        if char == "[":
            return self._seq()
        if char == "{":
            return self._mapping()
        return self._scalar()

    def _seq(self):
        self.pos += 1
        items = []
        self._skip()
        if self.text[self.pos : self.pos + 1] == "]":
            self.pos += 1
            return items
        while True:
            items.append(self.value())
            self._skip()
            char = self.text[self.pos : self.pos + 1]
            self.pos += 1
            if char == "]":
                return items
            if char != ",":
                self._fail("expected , or ]")

    def _mapping(self):
        self.pos += 1
        result = {}
        self._skip()
        if self.text[self.pos : self.pos + 1] == "}":
            self.pos += 1
            return result
        while True:
            self._skip()
            colon = self.text.find(":", self.pos)
            if colon < 0:
                self._fail("expected key:")
            key = self.text[self.pos : colon].strip()
            if not key or key in result:
                self._fail("bad or duplicate key")
            self.pos = colon + 1
            result[key] = self.value()
            self._skip()
            char = self.text[self.pos : self.pos + 1]
            self.pos += 1
            if char == "}":
                return result
            if char != ",":
                self._fail("expected , or }")

    def _scalar(self):
        char = self.text[self.pos]
        if char in "\"'":
            return self._quoted(char)
        start = self.pos
        while self.pos < len(self.text) and self.text[self.pos] not in ",]}":
            self.pos += 1
        raw = self.text[start : self.pos].strip()
        if not raw:
            self._fail("empty scalar")
        return raw

    def _quoted(self, quote):
        start = self.pos
        self.pos += 1
        while self.pos < len(self.text):
            char = self.text[self.pos]
            if char == "\\" and quote == '"':
                self.pos += 2
                continue
            if char == quote:
                self.pos += 1
                chunk = self.text[start : self.pos]
                if quote == "'":
                    return chunk[1:-1].replace("''", "'")
                try:
                    return json.loads(chunk)
                except json.JSONDecodeError:
                    self._fail("bad quoted scalar")
            self.pos += 1
        self._fail("unterminated quote")
