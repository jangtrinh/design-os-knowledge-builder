"""frozen-source objects: a page or publisher with the frozen captures that back its claims."""

import hashlib
import re

from knowledge_builder.ontology.cited_paths import resolve_inside, run_of
from knowledge_builder.ontology.objects import format_error

SOURCE_INTERFACE = "frozen-source"
FIRST_PARTY, LOCAL_PUBLISHER = "first-party", "local"
HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")
CAPTURE_KEYS = ("evidence_uri", "sha256", "fetched")


def source_failures(ontology, graph, root):
    failures = []
    for obj in graph.all:
        if obj.data and obj.object_type and ontology.implements(obj.object_type, SOURCE_INTERFACE):
            failures.extend(_one(obj, root))
    return failures


def _one(obj, root):
    failures = []
    url = obj.data.get("url")
    if url is not None and (not isinstance(url, str) or not url.strip()):
        failures.append(format_error(obj.rel, "url must be a non-empty string", "/url"))
    captures = obj.data.get("captures")
    if captures is None:
        return failures
    if not isinstance(captures, list) or not captures:
        return failures + [format_error(obj.rel, "captures must be a non-empty list", "/captures")]
    seen = set()
    for index, item in enumerate(captures):
        pointer = f"/captures/{index}"
        problem = _shape(item)
        if problem:
            failures.append(format_error(obj.rel, problem, pointer))
            continue
        if item["evidence_uri"] in seen:
            failures.append(format_error(obj.rel, f"capture {item['evidence_uri']} is listed twice", pointer))
        seen.add(item["evidence_uri"])
        failures.extend(_capture_failures(obj.rel, item, root, pointer))
    return failures


def _shape(item):
    if not isinstance(item, dict) or set(item) != set(CAPTURE_KEYS):
        return "capture must be {evidence_uri, sha256, fetched}"
    if not all(isinstance(item[key], str) and item[key].strip() for key in CAPTURE_KEYS):
        return "capture values must be non-empty strings"
    return None


def _capture_failures(rel, item, root, pointer):
    uri = item["evidence_uri"]
    path = resolve_inside(root, uri)
    if path is None or run_of(root, uri) is None:
        return [format_error(rel, f"evidence_uri {uri} must be a file under _evidence/<run>/sources/", pointer + "/evidence_uri")]
    if HEX64.fullmatch(item["sha256"]) is None:
        return [format_error(rel, f"sha256 is not 64 hex for {uri}", pointer + "/sha256")]
    if not path.is_file():
        return [format_error(rel, f"missing capture file {uri}", pointer + "/evidence_uri")]
    if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"].lower():
        return [format_error(rel, f"sha256 mismatch for {uri}", pointer + "/sha256")]
    return []


def counts_as_independent(source_data):
    """First-party Sources (local execution output, authored examples) never add to independence."""
    return source_data.get("kind") != FIRST_PARTY
