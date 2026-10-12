"""ease:source attribute grammar and visible markdown headings.

A quoted value ends at the first matching quote. The next attribute needs
whitespace. Leftover text, a second copy of the same name, and an unclosed
quote are errors. Headings count only outside HTML comments, ``` and ~~~
fences, and four-space indented code. An unclosed comment hides the rest.
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
            if index < length and not body[index].isspace():
                raise AnchorSyntaxError("attributes must be separated by whitespace")
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


def _consume_comments(line, in_comment):
    """Return text outside HTML comments, and whether a comment is still open."""
    visible = []
    index = 0
    while index < len(line):
        if in_comment:
            end = line.find("-->", index)
            if end < 0:
                return "".join(visible), True
            in_comment = False
            index = end + 3
            continue
        start = line.find("<!--", index)
        if start < 0:
            visible.append(line[index:])
            break
        visible.append(line[index:start])
        index = start + 4
        in_comment = True
    return "".join(visible), in_comment


def _is_indented_code(line):
    """A 4-space or tab indented line is a code line, not a heading."""
    if line.strip() == "":
        return False
    return line.startswith("\t") or line.startswith("    ")


def _opens_fence(line):
    """Opening ``` or ~~~ fence. None when the line is not one."""
    if line.startswith("\t"):
        return None
    stripped = line.lstrip(" ")
    if len(line) - len(stripped) > 3:
        return None
    matched = re.match(r"(`{3,}|~{3,})", stripped)
    if not matched:
        return None
    marks = matched.group(1)
    return marks[0], len(marks)


def _closes_fence(line, char, length):
    if line.startswith("\t"):
        return False
    stripped = line.lstrip(" ")
    if len(line) - len(stripped) > 3:
        return False
    matched = re.match("(" + re.escape(char) + "{3,})[ \t]*$", stripped)
    return matched is not None and len(matched.group(1)) >= length


def visible_lines(text):
    """Lines outside HTML comments, fenced code, and indented code blocks.

    An unclosed <!-- comment hides every later line. Fences are ``` or ~~~.
    A heading indented by four spaces is code and does not count.
    """
    visible = []
    in_comment = False
    fence_char = ""
    fence_len = 0
    for raw in text.splitlines():
        if fence_char:
            if _closes_fence(raw, fence_char, fence_len):
                fence_char = ""
                fence_len = 0
            continue
        content, in_comment = _consume_comments(raw, in_comment)
        if in_comment and content.strip() == "":
            continue
        if _is_indented_code(raw):
            continue
        opener = _opens_fence(content)
        if opener is not None:
            fence_char, fence_len = opener
            continue
        visible.append(content)
    return visible


def heading_present(lines, heading):
    """True when a visible line is the heading, or the heading plus a suffix."""
    for line in lines:
        stripped = line.strip()
        if stripped == heading or stripped.startswith(heading + " ") or stripped.startswith(heading + "\t"):
            return True
    return False
