"""Scratch roots for the ontology-first tests: starter ontology, one run, hand-written claim/source/document files."""

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests.test_ontology_support import run_cli

TEMPLATES = Path(__file__).resolve().parent.parent / "src" / "knowledge_builder" / "templates"
RUN = "r1"
FETCHED = "2026-10-13T05:00:00+00:00"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def scaffold_root(root):
    """Starter ontology, _templates, claims/ and sources/ dirs, and run r1 (no atoms)."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    shutil.copy(TEMPLATES / "ontology.starter.yaml", root / "ontology.yaml")
    shutil.copytree(TEMPLATES / "_templates", root / "_templates")
    (root / "claims").mkdir()
    (root / "sources").mkdir()
    code, out, err = run_cli(["knowledge-builder", "run", "init", "--root", str(root), "--id", RUN, "--budget", "50"])
    assert code == 0, out + err
    return root


def freeze(root, stem, body, url=None, run=RUN):
    """Write a frozen capture with a leading Source-URL/Fetched header. Returns (uri, sha256)."""
    url = url or f"https://{stem}.example.com/page"
    path = Path(root) / "_evidence" / run / "sources" / f"{stem}.txt"
    data = f"Source-URL: {url}\nFetched: {FETCHED}\n\n{body}\n".encode("utf-8")
    path.write_bytes(data)
    return f"_evidence/{run}/sources/{stem}.txt", sha(data)


def add_atom(root, atom_id, stem, body, quote=None, claim_type="FACT", url=None, run=RUN, statement=None, extra=None):
    """Freeze a capture and append one atom for it to the run ledger."""
    uri, digest = freeze(root, stem, body, url=url, run=run)
    meta = {"claim": f"c-{atom_id}", "url": url or f"https://{stem}.example.com/page"}
    meta.update(extra or {})
    atom = {
        "id": atom_id, "run_id": run, "claim_type": claim_type,
        "statement": statement or f"Statement for {atom_id}.", "source_uri": uri, "source_digest": digest,
        "captured_at": FETCHED, "confidence": "HIGH", "verified_by_code": False, "metadata": meta,
        "quote": body if quote is None else quote,
    }
    with (Path(root) / "_evidence" / run / "evidence.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(atom) + "\n")
    return atom


def write_source(root, ident, uri, digest, kind="official", url="https://example.com/page", publisher="example.com"):
    text = f'''---
id: "{ident}"
title: "Page {ident}"
object_type: "source"
url: "{url}"
kind: "{kind}"
publisher: "{publisher}"
captures:
  - evidence_uri: "{uri}"
    sha256: "{digest}"
    fetched: "{FETCHED}"
---

## Capture

Frozen captures are listed in the captures property.
'''
    (Path(root) / "sources" / f"{ident}.md").write_text(text, encoding="utf-8")


def write_claim(root, ident, source, uri, quote, atom="a1", claim_type="FACT", statement=None, links=("supported-by",), run=RUN):
    statement = statement or quote
    link_rows = "".join(f'  - link_type: "{name}"\n    target_id: "{source if name == "supported-by" else name}"\n' for name in links)
    text = f'''---
id: "{ident}"
title: "{statement}"
object_type: "claim"
statement: "{statement}"
claim_type: "{claim_type}"
confidence: "HIGH"
atom_ids: ["{atom}"]
evidence:
  - atom: "{atom}"
    run: "{run}"
    source: "{source}"
    evidence_uri: "{uri}"
    quote: "{quote}"
link_types:
{link_rows}---

## Statement

{statement}

## Evidence

Quotes and captures are recorded in the evidence list of the frontmatter.
'''
    (Path(root) / "claims" / f"{ident}.md").write_text(text, encoding="utf-8")


def write_document(root, ident, cites, body_lines, source_uri, source_sha, object_type="concept", extra_links=()):
    links = "".join(f'  - link_type: "cites"\n    target_id: "{c}"\n' for c in cites)
    links += "".join(f'  - link_type: "{t}"\n    target_id: "{i}"\n' for t, i in extra_links)
    link_block = f"link_types:\n{links}" if links else ""
    core = "\n".join(body_lines)
    text = f'''---
id: "{ident}"
title: "Doc {ident}"
object_type: "{object_type}"
domain: "demo"
description: "Document {ident}."
when:
  - "demo"
trust_tier: "draft"
version: "1.0.0"
source_attribution:
  - uri: "{source_uri}"
    sha256: "{source_sha}"
{link_block}---

## Purpose

Demo.

## When to Use / When NOT

- **ALLOWED**: demo.

## Core Knowledge Content

{core}

## Failure Modes (Mandatory)

Demo.
'''
    (Path(root) / f"{ident}.md").write_text(text, encoding="utf-8")


def build_basic(root):
    """One atom -> source s1 -> claim c1 -> document doc-1 citing c1 with a claim anchor."""
    scaffold_root(root)
    atom = add_atom(root, "a1", "s1", "Alpha holds in every case.", quote="Alpha holds in every case.")
    write_source(root, "s1", atom["source_uri"], atom["source_digest"])
    write_claim(root, "c1", "s1", atom["source_uri"], "Alpha holds in every case.")
    write_document(root, "doc-1", ["c1"], ["Alpha holds in every case.", "<!-- ease:claim id=c1 -->"], atom["source_uri"], atom["source_digest"])
    return atom


class PackCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "pack"

    def read(self, rel):
        return (self.root / rel).read_text(encoding="utf-8")

    def write(self, rel, text):
        (self.root / rel).write_text(text, encoding="utf-8")

    def replace(self, rel, old, new):
        text = self.read(rel)
        assert old in text, (old, rel)
        self.write(rel, text.replace(old, new, 1))

    def verify(self, claims=True):
        from knowledge_builder.verify import verify_root

        return verify_root(self.root, claims=claims)[2]
