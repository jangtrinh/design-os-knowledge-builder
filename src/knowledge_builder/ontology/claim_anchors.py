"""`<!-- ease:claim id=<claim-id> -->`: a document cites a claim; the quote lives only in the claim."""

import re

from knowledge_builder.anchors import AnchorSyntaxError, parse_attributes

CLAIM_ANCHOR = re.compile(r"<!--\s*ease:claim\b(.*?)-->", re.DOTALL)
OPEN_CLAIM_ANCHOR = re.compile(r"<!--\s*ease:claim\b")


def claim_anchors(text):
    """One entry per anchor: its attribute map, or None when the attributes are malformed."""
    found = []
    for match in CLAIM_ANCHOR.finditer(text):
        try:
            found.append(parse_attributes(match.group(1)))
        except AnchorSyntaxError:
            found.append(None)
    return found


def well_formed_ids(text):
    """Claim ids of the anchors that are exactly `id=<non-empty>`; malformed anchors are skipped."""
    return [a["id"] for a in claim_anchors(text) if a is not None and set(a) == {"id"} and a["id"]]


def unclosed_count(text):
    return len(OPEN_CLAIM_ANCHOR.findall(text)) - len(CLAIM_ANCHOR.findall(text))
