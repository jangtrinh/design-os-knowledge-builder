"""Build a tiny ontology-first pack from a JSON spec by driving the real CLI. Prints the pack path.

Spec keys: topic, run, budget, researcher, sources, atoms, claims, documents, entities, links,
resolutions, state, review (see references/build-spec.md). Refuses an existing output directory.
Exit 0 built / 1 rejected (a CLI step refused) / 2 could not run.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from forge_common import CannotRun, product_src, run_cli  # noqa: E402

FETCHED = "2026-10-13T00:00:00+00:00"


class StepRejected(Exception):
    pass


def step(src, args, stdin=None):
    done = run_cli(src, args, stdin=stdin)
    if done.returncode != 0:
        raise StepRejected(f"{' '.join(map(str, args[:3]))}: {(done.stderr or done.stdout).strip()}")
    return done.stdout


def action(src, root, name, **params):
    pairs = []
    for key, value in params.items():
        for item in value if isinstance(value, list) else [value]:
            pairs += ["--param", f"{key}={item}"]
    step(src, ["action", name, "--root", root, *pairs])


def freeze(root, run, source):
    path = root / "_evidence" / run / "sources" / f"{source['stem']}.txt"
    data = f"Source-URL: {source['url']}\nFetched: {FETCHED}\n\n{source['body']}\n".encode("utf-8")
    path.write_bytes(data)
    return f"_evidence/{run}/sources/{source['stem']}.txt", hashlib.sha256(data).hexdigest()


def record_atoms(src, root, spec, captured):
    for atom in spec.get("atoms", []):
        uri, digest = captured[atom["source"]]
        meta = {"round": atom.get("round", 1), "novel": atom.get("novel", True), **atom.get("metadata", {})}
        body = {
            "id": atom["id"], "run_id": spec["run"], "claim_type": atom.get("claim_type", "FACT"),
            "statement": atom["statement"], "source_uri": uri, "source_digest": digest, "captured_at": FETCHED,
            "confidence": atom.get("confidence", "HIGH"), "verified_by_code": False, "metadata": meta,
            "quote": atom["quote"],
        }
        step(src, ["run", "record", "--root", root, "--id", spec["run"]], stdin=json.dumps(body))


def document_text(raw):
    allowed = "\n".join(f"- **ALLOWED**: {line}" for line in raw.get("allowed", ["Use as described."]))
    refused = "\n".join(f"- **NOT ALLOWED**: {line}" for line in raw.get("not_allowed", ["Outside the stated scope."]))
    core = []
    for item in raw.get("core", []):
        core.append(f"<!-- ease:claim id={item['claim']} -->" if isinstance(item, dict) else item)
    return (
        f"## Purpose\n\n{raw.get('purpose', raw['title'])}\n\n## When to Use / When NOT\n\n{allowed}\n{refused}\n\n"
        f"## Core Knowledge Content\n\n" + "\n".join(core) + f"\n\n## Failure Modes (Mandatory)\n\n{raw.get('failure_modes', 'None observed.')}\n"
    )


def write_body(path, body):
    text = path.read_text(encoding="utf-8")
    head = text[: text.index("\n---\n", 4) + 5]
    path.write_text(head + "\n" + body, encoding="utf-8")


def build_documents(src, root, spec):
    for raw in spec.get("documents", []):
        sources = [f"_evidence/{spec['run']}/sources/{stem}.txt" for stem in raw["source"]]
        action(src, root, "create-object", id=raw["id"], object_type=raw.get("object_type", "concept"), title=raw["title"],
               domain=raw.get("domain", "demo"), description=raw["description"], when=raw["when"], source=sources)
        write_body(root / f"{raw['id']}.md", document_text(raw))
        for item in raw.get("core", []):
            if isinstance(item, dict):
                action(src, root, "add-link", source=raw["id"], link_type="cites", target=item["claim"])


def build(spec, out, src):
    root, run = out, spec["run"]
    args = ["pack", "init", "--root", root, "--topic", spec["topic"], "--run", run, "--budget", spec.get("budget", 40)]
    if spec.get("researcher"):
        args += ["--researcher", spec["researcher"]]
    step(src, args)
    captured = {source["stem"]: freeze(root, run, source) for source in spec.get("sources", [])}
    record_atoms(src, root, spec, captured)
    for claim in spec.get("claims", []):
        params = {key: claim[key] for key in ("id", "publisher", "kind", "into", "contradicted_kind") if key in claim}
        action(src, root, "promote-claim", atom=claim["atom"], **params)
    for entity in spec.get("entities", []):
        action(src, root, "create-object", id=entity["id"], object_type=entity.get("object_type", "entity"), title=entity["title"])
    build_documents(src, root, spec)
    for link in spec.get("links", []):
        action(src, root, "add-link", source=link["source"], link_type=link["link_type"], target=link["target"])
    for item in spec.get("resolutions", []):
        action(src, root, "resolve-contradiction", claim=item["claim"], resolution=item["resolution"])
    for key, value in spec.get("state", {}).items():
        step(src, ["run", "state", "set", "--root", root, "--id", run, "--key", key, "--value", value])
    if spec.get("review"):
        (root / "_evidence" / run / "review.json").write_text(json.dumps(spec["review"], indent=2) + "\n", encoding="utf-8")
    step(src, ["index", "--root", root])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--spec", required=True, type=Path, help="JSON spec (see examples/)")
    parser.add_argument("--output-dir", required=True, type=Path, help="New directory for the pack")
    parser.add_argument("--repo-root", type=Path, default=None, help="knowledge-builder checkout (default: this repo or the installed package)")
    args = parser.parse_args()
    try:
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
        src = product_src(args.repo_root)
    except (OSError, ValueError, CannotRun) as exc:
        print(f"runtime: could not run: {exc}", file=sys.stderr)
        return 2
    out = args.output_dir.expanduser().resolve()
    if out.exists():
        print(f"output-dir: {out} exists; pick a new directory", file=sys.stderr)
        return 1
    try:
        build(spec, out, src)
    except (StepRejected, KeyError) as exc:
        print(f"build: {exc!r}" if isinstance(exc, KeyError) else f"build: {exc}", file=sys.stderr)
        return 1
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
