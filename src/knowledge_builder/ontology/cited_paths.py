"""Resolve a cited uri to a real path inside the knowledge root, or refuse it."""

from pathlib import Path

from knowledge_builder.containment import ContainmentError, real_path, require_inside


def resolve_inside(root, uri):
    """Real path of root/uri when it stays inside the real root; None for absolute, file:, empty or escaping uris."""
    if not isinstance(uri, str) or not uri.strip():
        return None
    uri = uri.strip()
    if uri.lower().startswith("file:") or uri.startswith(("/", "\\")) or Path(uri).is_absolute():
        return None
    try:
        return require_inside(Path(root) / uri, root)
    except ContainmentError:
        return None


def run_of(root, uri):
    """Run id when uri resolves to <root>/_evidence/<run>/sources/<file>; None otherwise."""
    real = resolve_inside(root, uri)
    if real is None:
        return None
    parts = real.relative_to(real_path(root)).parts
    if len(parts) >= 4 and parts[0] == "_evidence" and parts[2] == "sources":
        return parts[1]
    return None
