"""document -> cites -> claim -> supported-by -> source -> captures. Read-only traversal over the graph."""

from knowledge_builder.ontology.source_checks import counts_as_independent


class Chain:
    def __init__(self, claims, sources, captures):
        self.claims = claims      # claim objects the subject cites, or the subject itself
        self.sources = sources    # source objects behind them
        self.captures = captures  # [(source object, capture dict)] each claim's evidence actually rests on

    @property
    def rels(self):
        return {o.rel for o in [*self.claims, *self.sources]}

    def publishers(self):
        """Distinct publisher names, compared case-insensitively like the stopping gate does."""
        return {str(s.data["publisher"]).strip().lower() for s in self.sources
                if str(s.data.get("publisher") or "").strip() and counts_as_independent(s.data)}


def traverse(graph, obj):
    """Chain for a document (cites), a claim (evidence) or a source (captures); None for any other object."""
    if obj is None or not obj.data:
        return None
    if isinstance(obj.data.get("captures"), list):
        return Chain([], [obj], [(obj, c) for c in obj.data["captures"] if isinstance(c, dict)])
    if isinstance(obj.data.get("evidence"), list):
        return _of_claims(graph, [obj])
    cited = [graph.get(t) for kind, t in obj.links_out() if kind == "cites"]
    cited = [c for c in cited if c is not None and c.data]
    return _of_claims(graph, cited) if cited else None


def _of_claims(graph, claims):
    sources, captures, seen = [], [], set()
    for claim in claims:
        for entry in claim.data.get("evidence") or []:
            source = graph.get(entry.get("source")) if isinstance(entry, dict) else None
            if source is None or not source.data:
                continue
            if source.id not in seen:
                seen.add(source.id)
                sources.append(source)
            for capture in source.data.get("captures") or []:
                if isinstance(capture, dict) and capture.get("evidence_uri") == entry.get("evidence_uri"):
                    captures.append((source, capture))
    return Chain(claims, sources, captures)
