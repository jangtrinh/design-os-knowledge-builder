"""A publisher filed under more than one Source kind: a consistency warning, never a failure."""

from collections import defaultdict

from knowledge_builder.ontology.source_checks import SOURCE_INTERFACE
from knowledge_builder.pack.graph_counts import of_interface


def publisher_kind_conflicts(ontology, graph):
    """[{publisher, kinds}] for every publisher (case-insensitive) whose Sources carry two or more kinds."""
    kinds = defaultdict(set)
    for source in of_interface(ontology, graph, SOURCE_INTERFACE):
        publisher, kind = source.data.get("publisher"), source.data.get("kind")
        if isinstance(publisher, str) and publisher.strip() and isinstance(kind, str) and kind:
            kinds[publisher.strip().lower()].add(kind)
    return [{"publisher": name, "kinds": sorted(found)} for name, found in sorted(kinds.items()) if len(found) > 1]


def warning_lines(conflicts):
    return [f"warning: publisher {item['publisher']} appears as {', '.join(item['kinds'])}: pick one kind" for item in conflicts]
