"""ease:source attribute grammar and one markdown token pass.

A quoted value ends at the first matching quote. The next attribute needs
whitespace. Leftover text, a second copy of the same name, and an unclosed
quote are errors.

tokenize_document walks each line once. The states are normal, backtick fence,
tilde fence, indented code, and html comment. Comments are not recognised
inside a fence or indented code. Fences are not recognised inside a comment
or indented code. A heading is a normal-state line. An anchor is a complete
top-level <!-- ease:source ... --> comment. An unclosed comment hides the rest.
"""

from collections import namedtuple
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


Token = namedtuple("Token", ["line", "kind", "text"])

_ANCHOR_BODY = re.compile(r"\s*ease:source\b")


def tokenize_document(text):
    """Tokenise once. kind is text, blank, code, anchor, fence-open, fence-line, or fence-close."""
    tokens = []
    state = "normal"
    fence_char = ""
    fence_len = 0
    comment_body = []
    comment_line = 0

    def emit(line, kind, value):
        tokens.append(Token(line, kind, value))

    def flush_text(line, parts):
        value = "".join(parts).strip()
        parts.clear()
        if value:
            emit(line, "text", value)

    def scan(line, fragment):
        nonlocal state, comment_body, comment_line
        parts = []
        index = 0
        while index < len(fragment):
            start = fragment.find("<!--", index)
            if start < 0:
                parts.append(fragment[index:])
                break
            parts.append(fragment[index:start])
            end = fragment.find("-->", start + 4)
            if end < 0:
                flush_text(line, parts)
                state = "html comment"
                comment_body = [fragment[start + 4:]]
                comment_line = line
                return
            body = fragment[start + 4:end]
            if _ANCHOR_BODY.match(body):
                flush_text(line, parts)
                emit(line, "anchor", body)
            index = end + 3
        flush_text(line, parts)

    def handle_normal(line, raw):
        nonlocal state, fence_char, fence_len
        if raw.strip() == "":
            emit(line, "blank", "")
            return
        if _is_indented_code(raw):
            emit(line, "code", raw.strip())
            state = "indented code"
            return
        opener = _opens_fence(raw)
        if opener is not None:
            fence_char, fence_len = opener
            state = "backtick fence" if fence_char == "`" else "tilde fence"
            emit(line, "fence-open", raw.strip())
            return
        scan(line, raw)

    for line_no, raw in enumerate(text.splitlines(), 1):
        if state in ("backtick fence", "tilde fence"):
            if _closes_fence(raw, fence_char, fence_len):
                emit(line_no, "fence-close", raw.strip())
                state = "normal"
                fence_char = ""
                fence_len = 0
            else:
                shown = raw.strip()
                if shown:
                    emit(line_no, "fence-line", shown)
            continue
        if state == "html comment":
            end = raw.find("-->")
            if end < 0:
                comment_body.append("\n" + raw)
                continue
            comment_body.append("\n" + raw[:end])
            body = "".join(comment_body)
            if _ANCHOR_BODY.match(body):
                emit(comment_line, "anchor", body)
            comment_body = []
            state = "normal"
            rest = raw[end + 3:]
            if rest.strip():
                scan(line_no, rest)
            continue
        if state == "indented code":
            if raw.strip() == "" or _is_indented_code(raw):
                if raw.strip() == "":
                    emit(line_no, "blank", "")
                else:
                    emit(line_no, "code", raw.strip())
                continue
            state = "normal"
        handle_normal(line_no, raw)
    return tokens


def visible_lines(text):
    """Normal-state text, one string per source line.

    Fence lines, indented code, and comment text are omitted. An unclosed
    comment hides every later line. Same-line pieces stay on one line.
    """
    lines = []
    pending_line = None
    pending = []
    for tok in tokenize_document(text):
        if tok.kind != "text":
            continue
        if pending_line is None or tok.line != pending_line:
            if pending:
                lines.append(" ".join(pending))
            pending = [tok.text]
            pending_line = tok.line
        else:
            pending.append(tok.text)
    if pending:
        lines.append(" ".join(pending))
    return lines


def heading_present(lines, heading):
    """True when a visible line is the heading, or the heading plus a suffix."""
    for line in lines:
        stripped = line.strip()
        if stripped == heading or stripped.startswith(heading + " ") or stripped.startswith(heading + "\t"):
            return True
    return False
