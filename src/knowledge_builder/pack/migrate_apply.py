"""pack migrate --apply: build the ontology-first pack from a filled plan, every write through the action pipeline."""

import shutil
from pathlib import Path

from knowledge_builder.ontology.actions import ActionError, run_action, run_batch
from knowledge_builder.ontology.schema import load_ontology
from knowledge_builder.pack.check_pack import check_pack
from knowledge_builder.pack.init_pack import PackError, init_pack
from knowledge_builder.pack.migrate_body import cited_in_order, port_body
from knowledge_builder.pack.migrate_check import check_target, load_plan, plan_problems, starter_choices
from knowledge_builder.pack.migrate_plan import PLAN_FILE
from knowledge_builder.pack.migrate_scan import read_modules, read_runs, split_document
from knowledge_builder.research.ledger import AtomicResearchLedger, EvidenceAtom
from knowledge_builder.research.saturation import validate_round_metadata

ATOM_FIELDS = ("id", "claim_type", "statement", "source_uri", "source_digest", "captured_at", "confidence", "verified_by_code", "metadata", "quote")


def apply_plan(to_root, plan_path, from_root=None, run=None):
    """(exit code, lines). Refuses before writing; a failure after the first write removes everything it wrote."""
    to, plan = Path(to_root).expanduser(), load_plan(plan_path)
    if from_root and Path(from_root).expanduser().resolve() != Path(plan["from"]).resolve():
        raise PackError(f"--from {from_root} is not the root the plan was made from ({plan['from']})")
    if run and run != plan["run"]:
        raise PackError(f"--run {run} is not the run the plan names ({plan['run']})")
    check_target(to, plan_path)
    kinds, object_types = starter_choices()
    problems = plan_problems(plan, kinds, object_types)
    if problems:
        raise PackError(f"plan not applied, nothing written ({len(problems)} problem(s)):\n  " + "\n  ".join(problems))
    existed = to.exists()
    try:
        return _apply(to, plan)
    except Exception as exc:
        _wipe(to, existed)
        if isinstance(exc, PackError):
            raise
        raise PackError(f"migration failed, the target holds only {PLAN_FILE}: {exc}") from exc


def _apply(to, plan):
    root, run = Path(plan["from"]), plan["run"]
    init_pack(to, plan["topic"], run, plan["budget"], plan["required_claim_ids"], plan["researcher"], keep=(PLAN_FILE,))
    by_legacy = {item["legacy_uri"]: item for item in plan["sources"]}
    for item in plan["sources"]:
        target = to / item["evidence_uri"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / item["legacy_uri"], target)
    contradicts = {c["atom"]: c["contradicts"] for c in plan["contradictions"]}
    _record_atoms(to, root, plan, by_legacy, contradicts)
    run_batch(to, "promote-claim", _promotions(plan, by_legacy, contradicts))
    claim_of = {a["atom"]: a["claim_id"] for a in plan["anchors"]}
    for entry in plan["contradictions"]:
        if entry.get("resolution"):
            run_action(to, "resolve-contradiction", {"claim": claim_of[entry["atom"]], "resolution": entry["resolution"]})
    for module in plan["modules"]:
        params = {k: module[k] for k in ("title", "domain", "description", "when")}
        run_action(to, "create-object", {"id": module["id"], "object_type": module["object_type"], "source": module["source"], **params})
    cites = _port_bodies(to, root, plan)
    if cites:
        run_batch(to, "add-link", cites)
    code, lines = check_pack(to, run)
    return code, [f"[✓] migrated {len(plan['anchors'])} claim(s), {len(plan['modules'])} document(s) from {root}", *lines]


def _record_atoms(to, root, plan, by_legacy, contradicts):
    run = plan["run"]
    ledger = AtomicResearchLedger(run, base_dir=to / "_evidence")
    for legacy_run, data in read_runs(root).items():
        for atom in data["atoms"]:
            item = by_legacy.get(atom.get("source_uri"))
            if item is None:
                continue  # listed in the plan's skipped_atoms
            fields = {k: atom[k] for k in ATOM_FIELDS if k in atom}
            metadata = dict(fields.get("metadata") or {})
            metadata["v1_atom"] = legacy_run
            if atom["id"] in contradicts:
                metadata["contradicts"] = contradicts[atom["id"]]
            _record(ledger, {**fields, "run_id": run, "source_uri": item["evidence_uri"], "metadata": metadata})
    for anchor in plan["anchors"]:
        fill = anchor["backfill"]
        if fill is None:
            continue
        item = by_legacy[anchor["uri"]]
        metadata = {"backfill": True, **{k: v for k, v in (("claim", fill["claim"]), ("url", item["url"]), ("command", fill["command"])) if v}}
        _record(ledger, {
            "id": anchor["atom"], "run_id": run, "claim_type": fill["claim_type"], "statement": fill["statement"],
            "source_uri": item["evidence_uri"], "source_digest": item["sha256"], "captured_at": fill["captured_at"] or plan["created"],
            "confidence": fill["confidence"], "verified_by_code": fill["verified_by_code"], "metadata": metadata, "quote": anchor["quote"],
        })


def _record(ledger, fields):
    validate_round_metadata(fields.get("metadata"))
    ledger.record_atom(EvidenceAtom(**fields))


def _promotions(plan, by_legacy, contradicts):
    """One promote-claim item per anchor; atoms another atom contradicts go first so the contradiction finds its partner promoted."""
    partners = set(contradicts.values())
    source_of = {atom_id: by_legacy.get(uri) for uri, atom_id in _atom_files(plan)}
    items = []
    for anchor in plan["anchors"]:
        item = by_legacy[anchor["uri"]]
        entry = {"atom": anchor["atom"], "run": plan["run"], "id": anchor["claim_id"], "kind": item["kind"], "publisher": item["publisher"]}
        partner = source_of.get(contradicts.get(anchor["atom"]))
        if partner:
            entry["contradicted_kind"] = partner["kind"]
        items.append(entry)
    return sorted(items, key=lambda entry: entry["atom"] not in partners)


def _atom_files(plan):
    """(legacy uri, atom id) for every atom of the legacy ledgers."""
    for data in read_runs(Path(plan["from"])).values():
        for atom in data["atoms"]:
            yield atom.get("source_uri"), atom["id"]


def _port_bodies(to, root, plan):
    """Write each ported body under the frontmatter create-object made; return the cites links to add."""
    ontology, ids = load_ontology(to), {(a["uri"], a["quote"]): a["claim_id"] for a in plan["anchors"]}
    bodies = {m["path"]: m["body"] for m in read_modules(root)}
    links = []
    for module in plan["modules"]:
        folder = ontology.folder_of(module["object_type"])
        path = to / (f"{folder}/" if folder else "") / f"{module['id']}.md"
        front, _pending = split_document(path.read_text(encoding="utf-8"))
        ported = port_body(bodies[module["path"]], ids, module["path"])
        path.write_text(front + ported, encoding="utf-8")
        links.extend({"source": module["id"], "link_type": "cites", "target": cid} for cid in cited_in_order(ported))
    return links


def _wipe(to, existed):
    to = Path(to)
    if not to.exists():
        return
    if not existed:
        shutil.rmtree(to, ignore_errors=True)
        return
    for child in to.iterdir():
        if child.name == PLAN_FILE:
            continue
        shutil.rmtree(child, ignore_errors=True) if child.is_dir() and not child.is_symlink() else child.unlink(missing_ok=True)
