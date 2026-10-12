"""Newline-normalised substring check for a quote against a hashed file.

No model call. A blank quote does not match.
"""

from pathlib import Path


def normalise_newlines(text):
    """Collapse CR LF and bare CR to LF."""
    if not isinstance(text, str):
        return ""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def file_contains_quote(path, quote):
    """True when quote is a non-blank substring of path after newline normalisation."""
    if not isinstance(quote, str) or quote.strip() == "":
        return False
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False
    return normalise_newlines(quote) in normalise_newlines(text)
