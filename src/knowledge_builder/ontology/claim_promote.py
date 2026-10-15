"""promote-claim: ledger atom -> claims/<id>.md (+ sources/<id>.md, supported-by link). Plans edits only.

Native action: the edits are not expressible with the declarative verbs, but it runs through the same
pipeline (root lock, staged write, verify, rollback, index, log) as every other action.
"""

import json

from knowledge_builder.ontology.action_edits import EditError, add_link, set_key
from knowledge_builder.ontology.action_plan import ActionError, Stage
from knowledge_builder.ontology.claim_atoms import Atoms, header_field, verified_file
from knowledge_builder.ontology.claim_render import capture_rows, evidence_rows, render, template_for
from knowledge_builder.ontology.claim_state import PackState, host_of
from knowledge_builder.ontology.source_checks import FIRST_PARTY, LOCAL_PUBLISHER
from knowledge_builder.ontology.hosting_hosts import is_hosting_host
from knowledge_builder.ontology.list_edits import append_map_item

PARAMS = {"atom", "run", "into", "id", "kind", "publisher", "contradicted_kind"}


def plan_batch(root, ontology, graph, items):
    """(stage, [(params, stage file texts after that item)]). Items see each other's staged results."""
    state, atoms, stage, steps = PackState(ontology, graph), Atoms(root), Stage(root, graph), []
    for raw in items:
        params = _params(raw)
        try:
            _promote(root, state, atoms, stage, params)
        except (EditError, ValueError) as exc:
            raise ActionError(f"promote-claim {params['atom']}: {exc}") from exc
        steps.append((params, dict(stage.files)))
    return stage, steps


def _params(raw):
    for key, value in raw.items():
        if key not in PARAMS:
            raise ActionError(f"unknown parameter '{key}'; declared: {', '.join(sorted(PARAMS))}")
        if not isinstance(value, str) or not value.strip():
            raise ActionError(f"parameter '{key}' must be a non-empty string")
    if "atom" not in raw:
        raise ActionError("missing parameter 'atom'")
    if "into" in raw and "id" in raw:
        raise ActionError("parameters 'into' and 'id' exclude each other: --into extends a claim, id names a new one")
    return dict(raw)


def _promote(root, state, atoms, stage, params):
    run, atom = atoms.find(params["atom"], params.get("run"))
    _refuse_promoted(state, run, atom)
    if "into" in params:
        _into(root, state, stage, run, atom, params)
    else:
        _new(root, state, atoms, stage, run, atom, params)


def _refuse_promoted(state, run, atom):
    holder = state.promoted.get((run, atom.id))
    if holder:
        raise ActionError(f"atom '{atom.id}' is already promoted to claim '{holder}'")


def _new(root, state, atoms, stage, run, atom, params):
    links = []
    if atom.claim_type == "CONTRADICTION":
        other = (atom.metadata or {}).get("contradicts")
        if not isinstance(other, str) or not other:
            raise ActionError(f"atom '{atom.id}' is a CONTRADICTION without metadata.contradicts: record which atom it contradicts")
        other_run, other_atom = atoms.find(other, run)
        target = state.promoted.get((other_run, other_atom.id))
        if target is None:
            kind = params.get("contradicted_kind") or params.get("kind")
            target = _create_claim(root, state, stage, other_run, other_atom, None, kind, None)
        links.append(("contradicts", target))
    _create_claim(root, state, stage, run, atom, params.get("id"), params.get("kind"), params.get("publisher"), links)


def _create_claim(root, state, stage, run, atom, wanted_id, kind, publisher, links=()):
    real = verified_file(root, run, atom)
    source_id = _source_for(state, stage, run, atom, real, kind, publisher)
    ident = state.new_id(wanted_id, atom.statement)
    rel = state.rel(state.claim_type, ident)
    entry = _entry(run, atom, source_id)
    text = render(
        template_for(root, "claim"),
        {"id": ident, "title": " ".join(atom.statement.split())[:90], "statement": atom.statement,
         "claim_type": atom.claim_type, "confidence": atom.confidence},
        {"atom_ids": json.dumps([atom.id]), "evidence": evidence_rows(entry), "statement": atom.statement},
    )
    for link_type, target in [("supported-by", source_id), *links]:
        text = add_link(text, link_type, target)
    stage.files[rel] = text
    state.add_claim(ident, rel, {
        "claim_type": atom.claim_type, "status": "active", "atom_ids": [atom.id], "evidence": [entry],
        "link_types": [{"link_type": t, "target_id": i} for t, i in [("supported-by", source_id), *links]],
    })
    state.promoted[(run, atom.id)] = ident
    return ident


def _into(root, state, stage, run, atom, params):
    claim = state.claims.get(params["into"])
    if claim is None:
        raise ActionError(f"parameter 'into': unknown claim '{params['into']}'")
    data = claim.data
    if data.get("status") == "deprecated":
        raise ActionError(f"claim '{params['into']}' is deprecated: add the atom to its replacement")
    if data.get("claim_type") != atom.claim_type:
        raise ActionError(f"atom '{atom.id}' has claim_type {atom.claim_type}, claim '{params['into']}' is {data.get('claim_type')}")
    real = verified_file(root, run, atom)
    source_id = _source_for(state, stage, run, atom, real, params.get("kind"), params.get("publisher"))
    entry = _entry(run, atom, source_id)
    text = append_map_item(stage.read(claim.rel), "evidence", entry)
    atom_ids = [*data["atom_ids"], atom.id]
    text = set_key(text, "atom_ids", atom_ids)
    if not any(l.get("link_type") == "supported-by" and l.get("target_id") == source_id for l in data["link_types"]):
        text = add_link(text, "supported-by", source_id)
        data["link_types"] = [*data["link_types"], {"link_type": "supported-by", "target_id": source_id}]
    stage.files[claim.rel] = text
    data["atom_ids"], data["evidence"] = atom_ids, [*data["evidence"], entry]
    state.promoted[(run, atom.id)] = params["into"]


def _entry(run, atom, source_id):
    return {"atom": atom.id, "run": run, "source": source_id, "evidence_uri": atom.source_uri, "quote": atom.quote}


def _source_for(state, stage, run, atom, real, kind, publisher):
    """Id of the Source for this atom's page: reuse one with the same url, else create it."""
    url = (atom.metadata or {}).get("url") or header_field(real, "Source-URL")
    url = url.strip() if isinstance(url, str) and url.strip() else None
    if url is None and kind == FIRST_PARTY:
        url = f"local:{atom.source_uri}"  # the Source's url is required; a local file is named by its path
    if url is None:
        raise ActionError(
            f"atom '{atom.id}': no metadata.url and no Source-URL: header in the frozen file, so no Source can be named "
            f"(a local execution output or authored example takes --param kind={FIRST_PARTY})"
        )
    capture = {"evidence_uri": atom.source_uri, "sha256": atom.source_digest, "fetched": header_field(real, "Fetched") or atom.captured_at}
    existing = state.source_for_url(url)
    if existing is None:
        return _create_source(state, stage, url, capture, kind, publisher)
    source = state.sources[existing]
    captures = source.data.get("captures") or []
    for held in captures:
        if held.get("evidence_uri") == capture["evidence_uri"]:
            if held.get("sha256") != capture["sha256"]:
                raise ActionError(f"source '{existing}' already holds {held['evidence_uri']} with a different sha256")
            return existing
    stage.files[source.rel] = append_map_item(stage.read(source.rel), "captures", capture)
    source.data["captures"] = [*captures, capture]
    return existing


def _create_source(state, stage, url, capture, kind, publisher):
    allowed = (state.ontology.declared_properties(state.source_type).get("kind") or {}).get("values")
    if not kind or (allowed and kind not in allowed):
        raise ActionError(f"a new Source for {url} needs --param kind=<{'|'.join(allowed or ['kind'])}>, got {kind!r}")
    if kind == FIRST_PARTY:
        publisher = publisher or LOCAL_PUBLISHER
    else:
        host = host_of(url)
        if not publisher and is_hosting_host(host):
            raise ActionError(
                f"{host} hosts or mirrors other publishers' work, so it cannot name the publisher of {url}: "
                "pass --param publisher=<who published it>"
            )
        publisher = publisher or host
    if not publisher:
        raise ActionError(f"cannot derive a publisher from {url}: pass --param publisher=<name>")
    path = url.split("://", 1)[-1].split("?", 1)[0]
    ident = state.new_id(None, path)
    rel = state.rel(state.source_type, ident)
    stage.files[rel] = render(
        template_for(stage.root, "source"),
        {"id": ident, "title": path.rstrip("/"), "url": url, "kind": kind, "publisher": publisher},
        {"captures": capture_rows(capture)},
    )
    state.add_source(ident, rel, {"url": url, "captures": [capture]})
    return ident
