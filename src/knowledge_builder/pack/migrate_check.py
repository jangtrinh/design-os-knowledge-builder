"""pack migrate --apply: read the plan and refuse it, before anything is written, while it is not safe to apply."""

import json
import re
import tempfile
from collections import defaultdict
from pathlib import Path

from knowledge_builder.ontology.schema import load_ontology
from knowledge_builder.ontology.template_files import starter_ontology
from knowledge_builder.pack.init_pack import PackError
from knowledge_builder.pack.migrate_plan import PLAN_FILE, PLAN_VERSION
from knowledge_builder.pack.migrate_scan import sha256_of

KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FIRST_PARTY = "first-party"


def load_plan(path):
    try:
        plan = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PackError(f"cannot read plan {path}: {exc}") from exc
    keys = ("run", "from", "modules", "anchors", "sources", "contradictions", "legacy_runs", "topic")
    if not isinstance(plan, dict) or plan.get("plan_version") != PLAN_VERSION or any(k not in plan for k in keys):
        raise PackError(f"{path} is not a version {PLAN_VERSION} migration plan: run `pack migrate --plan` again")
    return plan


def check_target(to, plan_path):
    """The target holds nothing except the plan file."""
    to = Path(to).expanduser()
    if to.exists() and (not to.is_dir() or any(child.name != PLAN_FILE for child in to.iterdir())):
        raise PackError(f"--to is not empty: {to} (apply needs a new directory, or one that holds only {PLAN_FILE})")
    if to.exists() and (to / PLAN_FILE).exists() and Path(plan_path).resolve() != (to / PLAN_FILE).resolve():
        raise PackError(f"{to / PLAN_FILE} is not the plan being applied: delete it or apply that file")


def starter_choices():
    """(kinds a Source may have, object types a document may have) from the packaged starter ontology."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "ontology.yaml").write_text(starter_ontology(), encoding="utf-8")
        ontology = load_ontology(tmp)
    return ontology.declared_properties("source")["kind"]["values"], ontology.implementing("sourced-document")


def legacy_changes(plan):
    """What changed in the legacy root since the plan was written."""
    root, changed = Path(plan["from"]), []
    for module in plan["modules"]:
        path = root / module["path"]
        if not path.is_file() or sha256_of(path) != module["sha256"]:
            changed.append(module["path"])
    for item in plan["sources"]:
        path = root / item["legacy_uri"]
        if not path.is_file() or sha256_of(path) != item["sha256"]:
            changed.append(item["legacy_uri"])
    for run in plan["legacy_runs"]:
        ledger = root / "_evidence" / run["run"] / "evidence.jsonl"
        if run["ledger_sha256"] and (not ledger.is_file() or sha256_of(ledger) != run["ledger_sha256"]):
            changed.append(f"_evidence/{run['run']}/evidence.jsonl")
    return changed


def plan_problems(plan, kinds, object_types):
    problems = [f"{where}: {value}" for where, value in _needs(plan)]
    if not Path(plan["from"]).is_dir():
        problems.append(f"from: {plan['from']} is not a directory")
    elif (Path(plan["from"]) / "ontology.yaml").is_file():
        problems.append(f"from: {plan['from']} now has ontology.yaml")
    changed = legacy_changes(plan) if Path(plan["from"]).is_dir() else []
    if changed:
        problems.append("the legacy root changed since the plan was written, plan again: " + ", ".join(changed))
    problems.extend(_sources(plan, kinds))
    problems.extend(_ids(plan, object_types))
    for entry in plan["contradictions"]:
        if not isinstance(entry.get("contradicts"), str) or not entry["contradicts"].strip():
            problems.append(f"contradictions[{entry.get('atom')}].contradicts: needs the id of the atom it contradicts")
    return problems


def _needs(value, where=""):
    """Every string that still starts with NEEDS_, with a readable location."""
    if isinstance(value, str):
        if value.startswith("NEEDS_"):
            yield where, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _needs(item, f"{where}.{key}" if where else key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            label = next((item[k] for k in ("legacy_uri", "atom", "id", "claim_id") if isinstance(item, dict) and isinstance(item.get(k), str)), index)
            yield from _needs(item, f"{where}[{label}]")


def _sources(plan, kinds):
    problems, by_url = [], defaultdict(set)
    for item in plan["sources"]:
        where = f"sources[{item.get('legacy_uri')}]"
        if item.get("kind") not in kinds and not str(item.get("kind")).startswith("NEEDS_"):
            problems.append(f"{where}.kind: {item.get('kind')!r} is not one of {', '.join(kinds)}")
        if not isinstance(item.get("publisher"), str) or not item["publisher"].strip():
            problems.append(f"{where}.publisher: must be a non-empty string")
        if item.get("used") and not item.get("url") and item.get("kind") != FIRST_PARTY:
            problems.append(f"{where}.url: NEEDS_URL: the capture names no url; set url or use kind {FIRST_PARTY}")
        if item.get("used"):
            by_url[item.get("url")].add((item.get("kind"), item.get("publisher")))
    for url, pairs in by_url.items():
        if len({k for k, _p in pairs}) > 1:
            problems.append(f"sources with url {url} are given two kinds: one url is one Source, pick one")
        if len({p for _k, p in pairs}) > 1:
            problems.append(f"sources with url {url} are given two publishers: one url is one Source, pick one")
    return problems


def _ids(plan, object_types):
    problems, seen = [], {m.get("id") for m in plan["modules"]}
    for module in plan["modules"]:
        if module.get("object_type") not in object_types:
            problems.append(f"modules[{module.get('id')}].object_type: {module.get('object_type')!r} is not one of {', '.join(object_types)}")
        for field in ("when", "source"):
            values = module.get(field)
            if not isinstance(values, list) or not values or len(set(values)) != len(values) or not all(isinstance(v, str) and v for v in values):
                problems.append(f"modules[{module.get('id')}].{field}: must be a non-empty list of distinct strings")
    for anchor in plan["anchors"]:
        ident = anchor.get("claim_id")
        if not isinstance(ident, str) or not KEBAB.fullmatch(ident):
            problems.append(f"anchors[{ident}].claim_id: must be a kebab-case id")
        elif ident in seen:
            problems.append(f"claim id {ident} is used twice (claims and module ids share one namespace)")
        seen.add(ident)
    return problems
