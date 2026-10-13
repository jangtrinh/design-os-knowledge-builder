"""Errors shared by the ontology loader modules."""


class OntologyError(ValueError):
    """ontology.yaml is missing required structure or references something undeclared."""
