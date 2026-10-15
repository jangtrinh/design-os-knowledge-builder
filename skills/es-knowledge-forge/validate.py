"""Reject facts about a knowledge pack, offline and deterministic (never taste).

Checks, one `<check>: <what to fix>` line per failure:
contract, verify, index, uncited-claims, documents-without-claims, hosting-publisher,
publisher-kind, contradictions, review. Wraps `pack check` and `pack status --json`.
Exit 0 ok / 1 reject / 2 could not run.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from forge_common import SKILL_DIR, CannotRun, pack_objects, product_src, run_cli  # noqa: E402

CONTRACT = SKILL_DIR / "contract.txt"


def contract_failures():
    try:
        first, _, body = CONTRACT.read_bytes().partition(b"\n")
    except OSError:
        return ["contract: contract.txt is missing; regenerate it with scripts/generate-skill-contract.py"]
    expected = first.decode("utf-8", "replace").removeprefix("# sha256: ")
    if hashlib.sha256(body).hexdigest() != expected:
        return ["contract: contract.txt was edited by hand; regenerate it with scripts/generate-skill-contract.py"]
    return []


def tool_json(src, args):
    done = run_cli(src, args)
    if done.returncode != 0:
        raise CannotRun((done.stderr or done.stdout).strip() or f"{' '.join(args[:2])} exited {done.returncode}")
    return json.loads(done.stdout)


def verify_lines(src, root, run):
    done = run_cli(src, ["pack", "check", "--root", root, "--run", run])
    if done.returncode not in (0, 1):
        raise CannotRun((done.stderr or done.stdout).strip())
    lines = done.stdout.splitlines()
    out = []
    count = next((int(line.split(":")[1]) for line in lines if line.startswith("failures:")), 0)
    start = next((i for i, line in enumerate(lines) if line.startswith("failures:")), -1) + 1
    out += [f"verify: {line.strip()}" for line in lines[start:start + count]]
    for line in lines:
        if line.startswith("index: not fresh"):
            out.append(f"index: {line[7:]}")
    return out


def graph_failures(root, status):
    objects = pack_objects(root)
    cited = {target for _p, _s, links in objects.values() for kind, target in links if kind == "cites"}
    out = []
    uncited = sorted(i for i, (_p, s, _l) in objects.items() if s.get("object_type") == "claim" and i not in cited)
    if status["uncited_claims"]:
        names = uncited or ["(count only)"]
        out += [f"uncited-claims: claim {n} is cited by no document: add a cites link and an ease:claim anchor, or deprecate it" for n in names]
    bare = sorted(i for i, (_p, s, links) in objects.items()
                  if "source_attribution" in s and not any(k == "cites" for k, _t in links))
    if status["documents_without_claims"]:
        out += [f"documents-without-claims: document {n} cites no claim: promote claims and cite them" for n in bare or ["(count only)"]]
    return out


def hosting_failures(root):
    from knowledge_builder.ontology.hosting_hosts import is_hosting_host

    out = []
    for ident, (_path, scalars, _links) in pack_objects(root).items():
        publisher = scalars.get("publisher", "").strip().lower()
        if publisher and is_hosting_host(publisher):
            out.append(f"hosting-publisher: source {ident} names the hosting host {publisher} as publisher: pass publisher=<who wrote it> to promote-claim")
    return out


def contradiction_failures(root):
    objects = pack_objects(root)
    out = []
    for ident, (_path, scalars, links) in objects.items():
        if scalars.get("claim_type") != "CONTRADICTION":
            continue
        partners = [objects[t][1].get("status") for k, t in links if k == "contradicts" and t in objects]
        if scalars.get("resolution", "").strip() or scalars.get("status") == "deprecated" or "deprecated" in partners:
            continue
        out.append(f"contradictions: claim {ident} is an unresolved CONTRADICTION: run resolve-contradiction with a reason, or deprecate one side")
    return out


def review_failures(root, run):
    path = Path(root) / "_evidence" / run / "review.json"
    where = f"_evidence/{run}/review.json"
    if not path.is_file():
        return [f"review: {where} is missing: a reviewer on a different runtime must write it"]
    try:
        review = json.loads(path.read_text(encoding="utf-8"))
        state = json.loads((path.parent / "state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [f"review: {where} or state.json is not readable JSON: rewrite it as an object"]
    if not isinstance(review, dict):
        return [f"review: {where} is not a JSON object: rewrite it"]
    runtime = review.get("reviewer_runtime")
    if review.get("passed") is not True:
        return [f"review: {where} passed is not true: fix the findings and re-review"]
    if not isinstance(runtime, str) or not runtime.strip():
        return [f"review: {where} has no reviewer_runtime: name the runtime that reviewed"]
    if runtime == state.get("researcher_runtime"):
        return [f"review: reviewer_runtime equals researcher_runtime ({runtime}): review on a different runtime"]
    return []


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", required=True, type=Path, help="Pack root (ontology.yaml, claims/, sources/)")
    parser.add_argument("--run", default=None, help="Run id (default: pack.json)")
    parser.add_argument("--repo-root", type=Path, default=None, help="knowledge-builder checkout (default: this repo or the installed package)")
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    failures = contract_failures()
    try:
        if not (root / "ontology.yaml").is_file():
            raise CannotRun(f"{root} has no ontology.yaml: not an ontology-first pack")
        src = product_src(args.repo_root)
        if src is not None:
            sys.path.insert(0, str(src))
        status = tool_json(src, ["pack", "status", "--root", root, "--json", *(["--run", args.run] if args.run else [])])
        run = status["run"]
        if not run:
            raise CannotRun("pack has no run: pass --run or add pack.json")
        graph = graph_failures(root, status)
        bare = {line.split()[2] + ".md" for line in graph if line.startswith("documents-without-claims: document ")}
        failures += [line for line in verify_lines(src, root, run)
                     if not any(line.endswith(f"{name}: no claim was checked") for name in bare)]
        failures += graph
        failures += hosting_failures(root)
        failures += [f"publisher-kind: publisher {c['publisher']} appears as {', '.join(c['kinds'])}: pick one kind"
                     for c in status["publisher_kind_conflicts"]]
        failures += contradiction_failures(root)
        failures += review_failures(root, run)
    except (CannotRun, OSError, ValueError, KeyError, ImportError) as exc:
        print(f"runtime: could not run: {exc}", file=sys.stderr)
        return 2
    if failures:
        print("\n".join(failures))
        return 1
    gate = status["gate"]
    print("ok")
    print(f"gate: {gate['decision']} - {gate['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
