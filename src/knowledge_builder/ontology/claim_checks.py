"""evidence-claim objects: statement, evidence entries tied to sources and captures, contradictions."""

import json
import re

from knowledge_builder.anchors import visible_lines
from knowledge_builder.ontology.cited_paths import resolve_inside
from knowledge_builder.ontology.objects import format_error
from knowledge_builder.ontology.source_checks import SOURCE_INTERFACE
from knowledge_builder.quote_check import file_contains_quote, normalise_newlines

CLAIM_INTERFACE = "evidence-claim"
EVIDENCE_KEYS = ("atom", "run", "source", "evidence_uri", "quote")


def claim_failures(ontology, graph, root, claims=False):
    failures = []
    ledgers = {}
    for obj in graph.all:
        if obj.data and obj.object_type and ontology.implements(obj.object_type, CLAIM_INTERFACE):
            failures.extend(_structure(ontology, graph, obj))
            if claims:
                failures.extend(_against_files(graph, obj, root, ledgers))
    return failures


def _structure(ontology, graph, obj):
    data, failures = obj.data, []
    statement = data.get("statement")
    if statement is not None and (not isinstance(statement, str) or not statement.strip()):
        failures.append(format_error(obj.rel, "statement must be a non-empty string", "/statement"))
    elif isinstance(statement, str) and _section(obj.text, "## Statement") != _squash(statement):
        failures.append(format_error(obj.rel, "## Statement section must repeat the statement property", "/body"))
    links = dict.fromkeys(obj.links_out())
    if data.get("claim_type") == "CONTRADICTION" and not any(kind == "contradicts" for kind, _t in links):
        failures.append(format_error(obj.rel, "a CONTRADICTION claim needs a contradicts link", "/link_types"))
    evidence = data.get("evidence")
    if evidence is None:
        return failures
    entries = _entries(obj, evidence, failures)
    if [e["atom"] for e in entries] != (data.get("atom_ids") or []):
        failures.append(format_error(obj.rel, "atom_ids must list the evidence atoms in order", "/atom_ids"))
    supported = {target for kind, target in links if kind == "supported-by"}
    used = set()
    for index, entry in enumerate(entries):
        used.add(entry["source"])
        failures.extend(_entry_failures(ontology, graph, obj, entry, supported, f"/evidence/{index}"))
    for target in sorted(supported - used):
        failures.append(format_error(obj.rel, f"supported-by '{target}' has no evidence entry", "/link_types"))
    return failures


def _entries(obj, evidence, failures):
    if not isinstance(evidence, list) or not evidence:
        failures.append(format_error(obj.rel, "evidence must be a non-empty list", "/evidence"))
        return []
    good = []
    for index, item in enumerate(evidence):
        if isinstance(item, dict) and set(item) == set(EVIDENCE_KEYS) and all(isinstance(v, str) and v.strip() for v in item.values()):
            good.append(item)
        else:
            failures.append(format_error(obj.rel, "evidence entry must be {atom, run, source, evidence_uri, quote}", f"/evidence/{index}"))
    return good


def _entry_failures(ontology, graph, obj, entry, supported, pointer):
    source = graph.get(entry["source"])
    if source is None or not source.object_type or not ontology.implements(source.object_type, SOURCE_INTERFACE):
        return [format_error(obj.rel, f"evidence source '{entry['source']}' is not a source object", pointer + "/source")]
    failures = []
    if entry["source"] not in supported:
        failures.append(format_error(obj.rel, f"evidence source '{entry['source']}' needs a supported-by link", pointer + "/source"))
    if entry["evidence_uri"] not in _capture_uris(source):
        failures.append(format_error(obj.rel, f"{entry['evidence_uri']} is not a capture of source '{entry['source']}'", pointer + "/evidence_uri"))
    return failures


def _capture_uris(source):
    captures = (source.data or {}).get("captures")
    return {c.get("evidence_uri") for c in captures if isinstance(c, dict)} if isinstance(captures, list) else set()


def _against_files(graph, obj, root, ledgers):
    """claims mode: each quote occurs in its capture, and each atom is in the run ledger it names."""
    failures = []
    for index, entry in enumerate(_good(obj)):
        pointer = f"/evidence/{index}"
        path = resolve_inside(root, entry["evidence_uri"])
        if path is None or not path.is_file() or not file_contains_quote(path, entry["quote"]):
            failures.append(format_error(obj.rel, "quote is not in the capture file", pointer + "/quote"))
        atoms = _ledger(root, entry["run"], ledgers)
        record = atoms.get(entry["atom"])
        if record is None or record[0] != entry["evidence_uri"]:
            failures.append(format_error(obj.rel, f"atom '{entry['atom']}' is not in run '{entry['run']}' with this capture", pointer + "/atom"))
        elif isinstance(record[1], str) and record[1].strip() and normalise_newlines(entry["quote"]) != normalise_newlines(record[1]):
            failures.append(format_error(obj.rel, f"quote does not match atom '{entry['atom']}' in run '{entry['run']}'", pointer + "/quote"))
    return failures


def _good(obj):
    evidence = obj.data.get("evidence")
    return [e for e in evidence if isinstance(e, dict) and set(e) == set(EVIDENCE_KEYS)] if isinstance(evidence, list) else []


def _ledger(root, run, cache):
    """{atom id: (source_uri, quote)} for a run; an unreadable or absent ledger is empty."""
    if run not in cache:
        found = {}
        path = resolve_inside(root, f"_evidence/{run}/evidence.jsonl")
        try:
            for line in (path.read_text(encoding="utf-8").splitlines() if path and path.is_file() else []):
                row = json.loads(line) if line.strip() else {}
                if isinstance(row, dict) and isinstance(row.get("id"), str):
                    found[row["id"]] = (row.get("source_uri"), row.get("quote"))
        except (OSError, UnicodeError, ValueError):
            found = {}
        cache[run] = found
    return cache[run]


def _squash(text):
    return re.sub(r"\s+", " ", text).strip()


def _section(text, heading):
    """Visible text between heading and the next `## ` line, whitespace-squashed."""
    lines, out, inside = visible_lines(text), [], False
    for line in lines:
        if line.strip().startswith("## "):
            if inside:
                break
            inside = line.strip() == heading
        elif inside:
            out.append(line)
    return _squash(" ".join(out))
