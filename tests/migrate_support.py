"""A small UKMC.v1 pack (no ontology.yaml) for the pack migrate tests, and plan helpers."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tests.test_ontology_support import run_cli

LEGACY_RUN = "leg-1"
FETCHED = "2026-10-01T00:00:00+00:00"
VENDOR_URL = "https://docs.vendor.example/a"
PAPER_URL = "https://arxiv.org/abs/2401.00001"
UNUSED_URL = "https://unused.example/z"
ALPHA, BETA = "Alpha holds in every case.", "Beta needs a key."
GAMMA, DELTA, EPSILON = "Gamma is open world by default.", "Delta fails closed.", "Epsilon is declared once."
LOCAL = "exit 0 and output ok"
KINDS = {"vendor-a.txt": "official", "paper-b.txt": "academic", "local-run.txt": "first-party", "unused.txt": "community"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def snapshot(root):
    """{relative path: sha256} of every file under root."""
    root = Path(root)
    return {p.relative_to(root).as_posix(): sha(p.read_bytes()) for p in sorted(root.rglob("*")) if p.is_file()}


def _capture(directory, name, body, url=None):
    header = f"Source-URL: {url}\nFetched: {FETCHED}\n\n" if url else ""
    data = (header + body + "\n").encode("utf-8")
    (directory / name).write_bytes(data)
    return f"_evidence/{LEGACY_RUN}/sources/{name}", sha(data)


def _atom(ident, claim_type, uri, digest, quote, claim, url, **meta):
    metadata = {"claim": claim, "url": url, **meta}
    return {
        "id": ident, "run_id": LEGACY_RUN, "claim_type": claim_type, "statement": f"Statement of {ident}.",
        "source_uri": uri, "source_digest": digest, "captured_at": FETCHED, "confidence": "HIGH",
        "verified_by_code": "command" in meta, "metadata": metadata, "quote": quote,
    }


def _anchor(uri, digest, quote):
    return f'<!-- ease:source uri={uri} sha256={digest} quote="{quote}" -->'


def _module(ident, refs, core, failures):
    attribution = "".join(f'  - uri: "{uri}"\n    sha256: "{digest}"\n' for uri, digest in refs)
    return f'''---
id: "{ident}"
title: "Module {ident}"
domain: "demo"
description: "Module {ident} for the migrate tests."
when:
  - "migrating"
trust_tier: "draft"
version: "1.0.0"
source_attribution:
{attribution}---

## Purpose
Demo.

## When to Use / When NOT
- **ALLOWED**: demo.

## Core Knowledge Content
{core}
## Failure Modes
{failures}'''


def build_legacy(root):
    """Two modules, six distinct anchors (one without an atom, one repeated across modules), one contradiction."""
    root = Path(root)
    sources = root / "_evidence" / LEGACY_RUN / "sources"
    sources.mkdir(parents=True)
    vendor = _capture(sources, "vendor-a.txt", f"{ALPHA} {BETA}", VENDOR_URL)
    paper = _capture(sources, "paper-b.txt", f"{GAMMA} {DELTA} {EPSILON}", PAPER_URL)
    local = _capture(sources, "local-run.txt", LOCAL)
    unused = _capture(sources, "unused.txt", "never cited", UNUSED_URL)
    atoms = [
        _atom("a1", "FACT", *vendor, ALPHA, "c-alpha", VENDOR_URL, round=1, novel=True),
        _atom("a2", "FACT", *paper, GAMMA, "c-gamma", PAPER_URL, round=1, novel=True),
        _atom("a3", "FAILURE_MODE", *paper, DELTA, "c-gamma", PAPER_URL, round=2, novel=True),
        _atom("a4", "CONTRADICTION", *vendor, BETA, "c-alpha", VENDOR_URL, round=2),
        _atom("a5", "FACT", *unused, "never cited", "c-gamma", UNUSED_URL, round=2),
        _atom("a6", "FACT", *local, LOCAL, "c-alpha", "local-execution", command="python run.py"),
    ]
    run = root / "_evidence" / LEGACY_RUN
    (run / "evidence.jsonl").write_text("".join(json.dumps(a) + "\n" for a in atoms), encoding="utf-8")
    (run / "state.json").write_text(json.dumps({
        "run_id": LEGACY_RUN, "round": 2, "status": "RUNNING", "budget_used": 0, "budget_total": 50,
        "remaining_budget_calls": 50, "gaps": [], "resolved": ["a4"], "required_claim_ids": ["c-alpha", "c-gamma"],
        "minimum_independent_sources": 2, "researcher_runtime": "r-model",
        "resolution_notes": {"a4": "scope difference: documented disagreement"},
    }), encoding="utf-8")
    (root / "m-one.md").write_text(_module(
        "m-one", [vendor, paper],
        f"{ALPHA}\n{_anchor(*vendor[:2], ALPHA)}\n\n{BETA}\n{_anchor(*vendor[:2], BETA)}\n\n",
        f"- {DELTA}\n  {_anchor(*paper[:2], DELTA)}\n- {EPSILON}\n  {_anchor(*paper[:2], EPSILON)}\n",
    ), encoding="utf-8")
    (root / "m-two.md").write_text(_module(
        "m-two", [vendor, paper, local],
        f"{ALPHA}\n{_anchor(*vendor[:2], ALPHA)}\n\n{GAMMA}\n{_anchor(*paper[:2], GAMMA)}\n\n{LOCAL}\n{_anchor(*local[:2], LOCAL)}\n\n",
        "Derived: nothing else fails.\n",
    ), encoding="utf-8")
    return root


def fill_plan(path, kinds=None, publishers=None, contradicts="a1"):
    """Replace every NEEDS_* placeholder the way a reviewer would."""
    path = Path(path)
    plan = json.loads(path.read_text(encoding="utf-8"))
    kinds, publishers = kinds or KINDS, publishers or {"paper-b.txt": "Test Authors"}
    for item in plan["sources"]:
        name = Path(item["legacy_uri"]).name
        if item["kind"].startswith("NEEDS_"):
            item["kind"] = kinds[name]
        if item["publisher"].startswith("NEEDS_"):
            item["publisher"] = publishers[name]
    for item in plan["contradictions"]:
        if item["contradicts"].startswith("NEEDS_"):
            item["contradicts"] = contradicts
    path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return plan


def migrate(*args):
    return run_cli(["knowledge-builder", "pack", "migrate", *args])


class MigrateCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.legacy, self.to = build_legacy(base / "legacy"), base / "new"
        self.plan_path = self.to / "migration-plan.json"
        self.before = snapshot(self.legacy)

    def plan(self):
        return migrate("--from", str(self.legacy), "--to", str(self.to), "--run", "mig-1", "--plan")

    def apply(self, plan=None):
        return migrate("--to", str(self.to), "--apply", str(plan or self.plan_path))

    def load_plan(self):
        return json.loads(self.plan_path.read_text(encoding="utf-8"))

    def save_plan(self, plan):
        self.plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")

    def filled(self):
        code, out, err = self.plan()
        assert code == 0, out + err
        return fill_plan(self.plan_path)

    def names(self, folder):
        return sorted(p.name for p in (self.to / folder).glob("*.md"))
