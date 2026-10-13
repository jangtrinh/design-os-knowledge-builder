"""Flow-style values for ontology.yaml: `[a, b]`, `{k: v}`, quoted scalars."""

import json


class SchemaSyntaxError(ValueError):
    """ontology.yaml uses syntax outside the supported subset."""


class FlowParser:
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


def parse_inline(text, number):
    parser = FlowParser(text, number)
    value = parser.value()
    parser.finish()
    return value
