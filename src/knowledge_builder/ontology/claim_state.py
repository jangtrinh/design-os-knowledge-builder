"""What the graph already holds of a pack, kept current while one plan stages several promotions."""

import re
from types import SimpleNamespace
from urllib.parse import urlparse

from knowledge_builder.ontology.action_plan import ActionError
from knowledge_builder.ontology.claim_checks import CLAIM_INTERFACE
from knowledge_builder.ontology.schema import KEBAB
from knowledge_builder.ontology.source_checks import SOURCE_INTERFACE


def normal_url(url):
    return url.strip().rstrip("/")


def slug(text, limit):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:limit].strip("-")


def host_of(url):
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


class PackState:
    def __init__(self, ontology, graph):
        claim_types = [t for t in ontology.object_types if ontology.implements(t, CLAIM_INTERFACE)]
        source_types = [t for t in ontology.object_types if ontology.implements(t, SOURCE_INTERFACE)]
        if not claim_types or not source_types:
            raise ActionError("ontology.yaml needs an object type implementing evidence-claim and one implementing frozen-source")
        self.claim_type, self.source_type = sorted(claim_types)[0], sorted(source_types)[0]
        self.ontology = ontology
        self.taken = set(graph.by_id)
        self.claims, self.sources, self.promoted = {}, {}, {}
        for obj in graph.all:
            if not obj.data or not obj.object_type:
                continue
            if ontology.implements(obj.object_type, CLAIM_INTERFACE):
                self.claims[obj.id] = obj
                for entry in obj.data.get("evidence") or []:
                    if isinstance(entry, dict):
                        self.promoted[(entry.get("run"), entry.get("atom"))] = obj.id
            elif ontology.implements(obj.object_type, SOURCE_INTERFACE):
                self.sources[obj.id] = obj

    def rel(self, kind, ident):
        folder = self.ontology.folder_of(kind)
        return f"{folder}/{ident}.md" if folder else f"{ident}.md"

    def new_id(self, wanted, fallback):
        if wanted is not None:
            if KEBAB.fullmatch(wanted) is None or wanted in self.taken:
                raise ActionError(f"parameter 'id': '{wanted}' must be a new kebab-case id")
            return self.reserve(wanted)
        base, number = slug(fallback, 60) or "item", 1
        ident = base
        while ident in self.taken:
            number += 1
            ident = f"{base}-{number}"
        return self.reserve(ident)

    def reserve(self, ident):
        self.taken.add(ident)
        return ident

    def source_for_url(self, url):
        wanted = normal_url(url)
        for ident, obj in self.sources.items():
            if normal_url(str(obj.data.get("url", ""))) == wanted:
                return ident
        return None

    def add_claim(self, ident, rel, data):
        self.claims[ident] = SimpleNamespace(rel=rel, data=data)

    def add_source(self, ident, rel, data):
        self.sources[ident] = SimpleNamespace(rel=rel, data=data)
