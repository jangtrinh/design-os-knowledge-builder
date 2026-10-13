"""Read every knowledge object under a root into an in-memory graph. Read-only."""

from pathlib import Path

from knowledge_builder.containment import ContainmentError, read_text_inside, require_inside
from knowledge_builder.frontmatter import FrontmatterError, parse_frontmatter

SKIP_DIRS = {"_evidence", "_actions", "_templates"}
DEFAULT_STATUS = "experimental"


class KnowledgeObject:
    def __init__(self, rel, data, text, error=None):
        self.rel = rel
        self.data = data if isinstance(data, dict) else None
        self.text = text
        self.error = error
        ident = self.data.get("id") if self.data else None
        self.id = ident if isinstance(ident, str) and ident else Path(rel).stem

    @property
    def status(self):
        value = self.data.get("status") if self.data else None
        return value if value is not None else DEFAULT_STATUS

    @property
    def object_type(self):
        return self.data.get("object_type") if self.data else None

    def links_out(self):
        """Well-formed (link_type, target_id) pairs; malformed items are reported by link checks."""
        items = self.data.get("link_types") if self.data else None
        pairs = []
        for item in items if isinstance(items, list) else []:
            if isinstance(item, dict) and isinstance(item.get("link_type"), str) and isinstance(item.get("target_id"), str):
                pairs.append((item["link_type"], item["target_id"]))
        return pairs


class Graph:
    def __init__(self, root, objects):
        self.root = root
        self.all = objects
        self.by_id = {}
        for obj in objects:
            self.by_id.setdefault(obj.id, []).append(obj)

    def get(self, ident):
        found = self.by_id.get(ident)
        return found[0] if found else None

    def links_in(self, ident):
        pairs = []
        for obj in self.all:
            for link_type, target in obj.links_out():
                if target == ident:
                    pairs.append((link_type, obj.id))
        return sorted(pairs)


def format_error(rel, message, pointer="/"):
    return f"[ERROR] {rel} {message} in {pointer}"


def message_file(message):
    """File a verify failure line is about: `[ERROR] <file> ...` or `<file>: ...`."""
    if message.startswith("[ERROR] "):
        return message[8:].split(" ", 1)[0]
    return message.split(":", 1)[0]


def load_graph(root):
    root = Path(root).resolve()
    objects = []
    for path in sorted(_markdown_paths(root)):
        rel = path.relative_to(root).as_posix()
        try:
            text = read_text_inside(path, root)
            objects.append(KnowledgeObject(rel, parse_frontmatter(text), text))
        except (ContainmentError, OSError, UnicodeError, FrontmatterError) as exc:
            objects.append(KnowledgeObject(rel, None, "", error=str(exc)))
    return Graph(root, objects)


def _markdown_paths(root):
    for path in root.rglob("*"):
        if path.suffix.lower() != ".md":
            continue
        relative = path.relative_to(root)
        if SKIP_DIRS.intersection(relative.parts) or path.name.lower() == "readme.md":
            continue
        if path.is_dir():
            continue
        try:
            require_inside(path, root)
        except ContainmentError:
            continue
        if path.is_file():
            yield path
