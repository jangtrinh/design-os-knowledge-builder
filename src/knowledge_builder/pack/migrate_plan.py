"""pack migrate --plan: scan a UKMC.v1 root and write migration-plan.json. Writes nothing else."""

import json
from datetime import datetime, timezone
from pathlib import Path

from knowledge_builder.pack.init_pack import PackError
from knowledge_builder.pack.migrate_derive import (
    assign_claim_ids, backfill, contradiction_rows, flat_atoms, free_id, source_entry,
)
from knowledge_builder.pack.migrate_scan import (
    KNOWN_KEYS, module_anchors, read_captures, read_modules, read_runs,
)

PLAN_FILE = "migration-plan.json"
PLAN_VERSION = 1
DEFAULT_BUDGET = 400
SINGLE_SEGMENT = ("", ".", "..")


def write_plan(legacy_root, to_root, run, topic=None):
    """Scan legacy_root, write <to_root>/migration-plan.json, return (path, plan)."""
    legacy, to = Path(legacy_root).expanduser(), Path(to_root).expanduser()
    if not legacy.is_dir():
        raise PackError(f"--from is not a directory: {legacy}")
    if (legacy / "ontology.yaml").is_file():
        raise PackError(f"{legacy} already has ontology.yaml: it is an ontology pack, nothing to migrate")
    if run in SINGLE_SEGMENT or "/" in run or "\\" in run:
        raise PackError(f"--run must be one path segment, got {run!r}")
    if _inside(to, legacy) or _inside(legacy, to):
        raise PackError("--from and --to must be separate directories (the legacy root is never written)")
    if (to / PLAN_FILE).exists():
        raise PackError(f"{to / PLAN_FILE} already exists: edit it and run --apply, or delete it to plan again")
    if to.exists() and (not to.is_dir() or any(to.iterdir())):
        raise PackError(f"--to is not empty: {to} (a migration target is a new or empty directory)")
    plan = build_plan(legacy.resolve(), run, topic)
    to.mkdir(parents=True, exist_ok=True)
    (to / PLAN_FILE).write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return to / PLAN_FILE, plan


def _inside(path, parent):
    path, parent = path.resolve(), parent.resolve()
    return path == parent or parent in path.parents


def build_plan(root, run, topic=None):
    runs = read_runs(root)
    if not runs:
        raise PackError(f"{root} has no _evidence/<run>/ ledger or captures: nothing to migrate")
    atoms = flat_atoms(runs)
    by_uri = {}
    for atom in atoms:
        by_uri.setdefault(atom.get("source_uri"), []).append(atom)
    captures = read_captures(root, runs, by_uri)
    new_uri = {}
    for uri, item in captures.items():
        target = f"_evidence/{run}/sources/{item['rel']}"
        if target in new_uri.values():
            raise PackError(f"two legacy runs hold a capture named {item['rel']}: rename one before migrating")
        new_uri[uri] = target
    modules, problems = _modules(read_modules(root), captures, new_uri)
    anchors = _anchors(modules, captures, by_uri, atoms, problems)
    assign_claim_ids(anchors, {m["id"] for m in modules}, atoms)
    contradictions = contradiction_rows(anchors, atoms, runs)
    partners = {c["contradicts"] for c in contradictions}
    used = {a["uri"] for a in anchors} | {a["source_uri"] for a in atoms if a["id"] in partners}
    skipped = [{"atom": a["id"], "reason": f"source_uri {a.get('source_uri')} is not a capture"} for a in atoms if a.get("source_uri") not in captures]
    if problems:
        raise PackError("cannot plan:\n  " + "\n  ".join(problems))
    states = [r["state"] for r in runs.values()]
    return {
        "plan_version": PLAN_VERSION, "from": str(root), "run": run, "topic": topic or root.name,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "budget": max([s.get("budget_total") for s in states if isinstance(s.get("budget_total"), int)] or [DEFAULT_BUDGET]),
        "researcher": next((s["researcher_runtime"] for s in states if s.get("researcher_runtime")), None),
        "required_claim_ids": list(dict.fromkeys(i for s in states for i in s.get("required_claim_ids") or [])),
        "legacy_runs": [{"run": r, "atoms": len(v["atoms"]), "ledger_sha256": v["ledger_sha256"], "state_sha256": v["state_sha256"]} for r, v in runs.items()],
        "modules": [{k: v for k, v in m.items() if k not in ("front", "body", "anchors")} for m in modules],
        "anchors": [{k: v for k, v in a.items() if k not in ("above", "heading")} for a in anchors],
        "sources": [source_entry(uri, item, new_uri[uri], uri in used) for uri, item in captures.items()],
        "contradictions": contradictions,
        "skipped_atoms": skipped,
    }


def _modules(found, captures, new_uri):
    modules, problems = [], []
    for item in found:
        front, label = item["front"], item["path"]
        missing = [k for k in ("id", "title", "domain", "description", "when", "source_attribution") if not front.get(k)]
        if missing:
            problems.append(f"{label}: missing {', '.join(missing)} (run `verify --legacy` and fix the module first)")
            continue
        sources = [s.get("uri") for s in front["source_attribution"] if isinstance(s, dict)]
        for uri in sources:
            if uri not in captures:
                problems.append(f"{label}: source_attribution {uri} is not a capture under _evidence/<run>/sources/")
        kind = front.get("object_type") if front.get("object_type") in ("concept", "guide", "comparison", "decision-record") else "concept"
        modules.append({
            "id": front["id"], "path": item["path"], "sha256": item["sha256"], "object_type": kind, "title": front["title"],
            "domain": front["domain"], "description": front["description"], "when": list(front["when"]),
            "source": [new_uri[u] for u in sources if u in new_uri], "legacy_trust_tier": front.get("trust_tier"),
            "legacy_version": front.get("version"), "unported_keys": sorted(set(front) - KNOWN_KEYS),
            "anchors": module_anchors(item),
        })
    return modules, problems


def _anchors(modules, captures, by_uri, atoms, problems):
    exact = {}
    for atom in atoms:
        exact.setdefault((atom.get("source_uri"), atom.get("quote")), atom)
    ids, anchors = {a["id"] for a in atoms}, {}
    for module in modules:
        for hit in module["anchors"]:
            key = (hit["uri"], hit["quote"])
            if hit["uri"] not in captures:
                problems.append(f"{module['path']}: anchor cites {hit['uri']}, which is not a capture under _evidence/<run>/sources/")
                continue
            if key not in anchors:
                anchors[key] = {"claim_id": None, "uri": hit["uri"], "quote": hit["quote"], "atom": None, "backfill": None, "modules": {}, "heading": hit["heading"], "above": hit["above"]}
                match = exact.get(key)
                if match:
                    anchors[key]["atom"] = match["id"]
                else:
                    anchors[key]["atom"] = free_id(ids)
                    anchors[key]["backfill"] = backfill(hit, by_uri.get(hit["uri"], []), captures[hit["uri"]])
            anchors[key]["modules"][module["id"]] = anchors[key]["modules"].get(module["id"], 0) + 1
    return list(anchors.values())
