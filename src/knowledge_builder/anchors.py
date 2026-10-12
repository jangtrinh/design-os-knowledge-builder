"""ease:source attribute grammar and visible markdown headings.

A quoted value ends at the first matching quote. Leftover text, a second
copy of the same name, and an unclosed quote are errors. Headings count
only outside HTML comments and fenced code.
"""

import re


class AnchorSyntaxError(ValueError):
    """The anchor attribute region is not the grammar."""


_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def parse_attributes(body):
    """Parse one attribute region. Raise AnchorSyntaxError on any leftover."""
    attrs = {}
    index = 0
    length = len(body)
    while True:
        while index < length and body[index].isspace():
            index += 1
        if index >= length:
            return attrs
        matched = _NAME.match(body, index)
        if not matched:
            raise AnchorSyntaxError("unconsumed attribute text")
        name = matched.group(0)
        index = matched.end()
        if index >= length or body[index] != "=":
            raise AnchorSyntaxError("malformed attribute")
        index += 1
        if index >= length:
            raise AnchorSyntaxError("missing attribute value")
        if body[index] in "\"'":
            quote = body[index]
            end = body.find(quote, index + 1)
            if end < 0:
                raise AnchorSyntaxError("unclosed quote")
            value = body[index + 1:end]
            index = end + 1
        else:
            start = index
            while index < length and not body[index].isspace():
                index += 1
            value = body[start:index]
            if value == "":
                raise AnchorSyntaxError("missing attribute value")
        if name in attrs:
            raise AnchorSyntaxError(f"duplicate attribute {name}")
        attrs[name] = value


def visible_lines(text):
    """Lines that are neither inside an HTML comment nor a fenced code block."""
    without_comments = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    lines = []
    in_fence = False
    for line in without_comments.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            lines.append(line)
    return lines


def heading_present(lines, heading):
    """True when a visible line is the heading, or the heading plus a suffix."""
    for line in lines:
        stripped = line.strip()
        if stripped == heading or stripped.startswith(heading + " ") or stripped.startswith(heading + "\t"):
            return True
    return False
