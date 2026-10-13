"""Which files the UKMC.v1 document checks apply to."""

DOCUMENT_INTERFACE = "sourced-document"


def v1_applies(ontology, data):
    """True in legacy mode and for every object that implements sourced-document.

    A file with no readable frontmatter, no object_type, or an undeclared one keeps the v1 checks;
    the ontology checks report the missing or wrong object_type. A declared type that does not
    implement sourced-document (claim, source, entity) is checked by its own interface instead.
    """
    if ontology is None:
        return True
    kind = data.get("object_type") if isinstance(data, dict) else None
    if kind not in ontology.object_types:
        return True
    return ontology.implements(kind, DOCUMENT_INTERFACE)


def claim_anchor_kinds(ontology):
    return ("source",) if ontology is None else ("source", "claim")
