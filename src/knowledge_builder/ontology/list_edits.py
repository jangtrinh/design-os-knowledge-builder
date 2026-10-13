"""Append one map item to a block list in frontmatter (claim evidence, source captures)."""

import json

from knowledge_builder.ontology.action_edits import EditError, _block_end, _eol, _find_key, _frontmatter


def append_map_item(text, key, fields):
    """Add `- k: v` rows (values JSON-quoted) at the end of the block list under key. Other lines stay byte-identical."""
    lines, close = _frontmatter(text)
    eol = _eol(lines)
    start = _find_key(lines, close, key)
    if start is None:
        raise EditError(f"frontmatter has no '{key}' list")
    rows = [f"{'  - ' if i == 0 else '    '}{name}: {json.dumps(value, ensure_ascii=False)}{eol}" for i, (name, value) in enumerate(fields.items())]
    end = _block_end(lines, start, close)
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    return "".join(lines[:end] + rows + lines[end:])
