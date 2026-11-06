"""Quote length and capture-body rules shared by the gate, promote, and verify.

A quote matches only in the capture body: the text after the first blank line
when the file starts with a capture header, and the whole file otherwise.
The quote never matches inside that header.
"""

from knowledge_builder.quote_check import normalise_newlines

MIN_WORDS = 6
MIN_CHARS = 30
TOO_SHORT = "quote must be at least 6 words and 30 characters"
HEADER_PREFIXES = ("Source-URL:", "Fetched:", "Command:")


def quote_too_short(quote):
    """True unless quote has at least 6 words and 30 characters after newline normalisation."""
    if not isinstance(quote, str):
        return True
    text = normalise_newlines(quote)
    return len(text.split()) < MIN_WORDS or len(text) < MIN_CHARS


def capture_body(text):
    """Text a quote may match. Header lines before the first blank line are excluded."""
    norm = normalise_newlines(text if isinstance(text, str) else "")
    lines = norm.split("\n")
    if not lines or not any(lines[0].startswith(prefix) for prefix in HEADER_PREFIXES):
        return norm
    for index, line in enumerate(lines):
        if line.strip() == "":
            return "\n".join(lines[index + 1:])
    return ""


def quote_failure(text, quote):
    """None when quote may verify. A short quote reports the length rule first."""
    if not isinstance(quote, str) or quote.strip() == "":
        return "quote is not in the capture file"
    if quote_too_short(quote):
        return TOO_SHORT
    if normalise_newlines(quote) not in capture_body(text):
        return "quote is not in the capture file"
    return None
