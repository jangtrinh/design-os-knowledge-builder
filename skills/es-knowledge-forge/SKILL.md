---
name: es-knowledge-forge
description: "Use when building, checking or extending an ontology-first knowledge pack: frozen sources, quoted claims, cited documents, independent review, stopping gate."
metadata:
  author: DESIGN:OS
---

# Knowledge Forge

One workflow: Concept → Build → Check → Hand over → Adjust. Python ≥3.10, stdlib only. The product is
`design-os-knowledge-builder`; scripts find it in this checkout, via `--repo-root <checkout>`, `KNOWLEDGE_BUILDER_REPO`,
or an installed package. `K` = `python3 -m knowledge_builder.cli`, `P` = the pack root, `R` = the run id. A new pack starts only with `pack init`.
The pack lives apart from the tool (rule R16) at `<knowledge-root>/<domain>/<topic>`: `<project>/knowledge/<topic>/` or `~/Products/jang-knowledge/<domain>/<topic>/`.

## 1. Concept

Read [concepts.md](concepts.md) and turn the request into one buildable pack. Propose the schema as
`ontology.proposal.yaml` with a rationale, then ask the owner through AskUserQuestion (≤4 questions per round,
recommended option first). Do not build before the answer. Read the numbered [rules.md](rules.md) before the first write.

| Need | Choose | Limit |
| --- | --- | --- |
| New topic | Starter ontology + proposed additions | Owner approves the schema |
| Extend a pack | Keep its `ontology.yaml`; add atoms, claims, documents | No schema change without approval |
| Facts for one document | One document type, claims cited by anchor | 1-8 documents per pack |
| Existing legacy pack | `pack migrate`: plan, fill kinds/publishers, apply ([workflow](references/ontology-first-workflow.md)) | Legacy root is read only; `verify`, `gate`, `lint`, `index` on it need `--legacy`, `ingest` none |

When NOT to use: summarising without quotes, topics with no public or frozen source, storing knowledge inside the tool repo.

## 2. Build

The real pipeline, step by step, with closing conditions, is in
[references/ontology-first-workflow.md](references/ontology-first-workflow.md). Flags and parameters come from the generated
[contract.txt](contract.txt); never edit it. In order:

```sh
K pack init --root P --topic "<topic>" --run R --researcher <runtime>     # then proposal -> owner approval
K ingest --freeze <url> --root P --run R --stem <stem>                    # freeze before quoting
echo '<atom json>' | K run record --root P --id R                         # round + novel on every atom
K run measure --root P --id R --material --write-state                    # after each round
K action promote-claim --root P --param atom=<id> --param id=<claim-id>   # --into / --batch / publisher= / kind=
K action set-source --root P --param source=<source-id> --param publisher=<name>   # and/or kind=; fixes an existing Source
K action create-object --root P --param id=<id> --param object_type=<type> --param title=<t> ...
K action add-link --root P --param source=<doc> --param link_type=cites --param target=<claim>
K action resolve-contradiction --root P --param claim=<id> --param resolution="<reason>"
K run state set --root P --id R --key version_applicability --value not_applicable   # + version_reason
```

Document bodies carry `<!-- ease:claim id=<claim> -->` anchors, written between create-object and add-link, then
`K index --root P`. A different runtime writes `_evidence/R/review.json` (rule R12).
For fixtures and tiny packs, [build.py](build.py) runs the same CLI from a JSON spec
([references/build-spec.md](references/build-spec.md), [examples/tiny-document-pack.json](examples/tiny-document-pack.json),
[examples/tiny-entity-pack.json](examples/tiny-entity-pack.json)) into a new directory and prints its path:

```sh
python3 skills/es-knowledge-forge/build.py --spec skills/es-knowledge-forge/examples/tiny-entity-pack.json --output-dir /absolute/new-pack
```

## 3. Check

```sh
K pack check --root P
python3 skills/es-knowledge-forge/validate.py --root P
python3 skills/es-knowledge-forge/look.py --root P --sheet /absolute/look-sheet.png
```

[validate.py](validate.py): offline, deterministic; one `<check>: <what to fix>` line per failure; exit 0 ok, 1 reject,
2 could not run. Checks: contract, verify, index, uncited-claims, documents-without-claims, hosting-publisher,
publisher-kind, contradictions, review. It rejects facts, never taste. On `ok` it also prints the gate line.
The council report lists gaps (no FAILURE_MODE or BENCHMARK atom, a `verified_by_code` atom without `metadata.command`) and grants nothing.
[look.py](look.py) (sheet markup in [look_sheet.py](look_sheet.py), shared helpers in [forge_common.py](forge_common.py))
renders one sheet with headless Chrome/Chromium and measures L1-L4; read [look.md](look.md) and judge L5-L8 on the PNG.
Neither installs anything or uses the network. Machine checks do not grade whether the knowledge is right.

## 4. Hand over

Use these fields, keeping failures and missing checks:

```text
PACK: <absolute pack root>   RUN: <run id>
APPROVAL: <who approved ontology.yaml and when, or NOT ASKED>
VALIDATE: <exit and actual lines, or ok>
LOOK: <exit, sheet path, L1-L4 lines, your L5-L8 reading>
GATE: <gate line of pack check as printed; never "sufficient" unless it says STOP_SUFFICIENT>
REVIEW: <reviewer_runtime vs researcher_runtime, or MISSING>
LIMITS: <checks not run, sources single-publisher, open frictions>
```

Without a browser use exactly: `LOOK: NOT RUN — no browser (Chrome/Chromium) available.`
Never write "should work". Report checks run after the last edit only.

## 5. Adjust

Edit the schema proposal, sources or atoms, rerun build steps for the affected objects, rerun check. Do not hand-edit
claims, sources, captures, the [contract](contract.txt) or `index.json`.

| What goes wrong | Do this instead |
| --- | --- |
| `verify:` line | Fix what it names; rules R2, R5, R9, R15 |
| `hosting-publisher` / `publisher-kind` | Re-promote with `publisher=<author org>` and one `kind`; R6, R7 |
| `uncited-claims` / `documents-without-claims` | Anchor + `cites` link, or deprecate the claim; R9 |
| `contradictions` | `resolve-contradiction` with a reason; R11 |
| `review` | Another runtime writes review.json; R12 |
| `index` | `K index --root P`; R14 |
| promote-claim: no `metadata.url` and no `Source-URL:` header | A local execution output or authored example takes `--param kind=first-party` (publisher `local`, never counted as independent); a web page keeps its `metadata.url` |
| A rejected action is not in `_actions/actions.jsonl` (successes only) | Read `_actions/rejected.jsonl` (action, params, reason, at); `pack status` shows the count |
| `query --linked-to <unknown id>` exits 1 `unknown object` (also unknown `--implements` / `--object-type`) | Fix the id: `K query --root P --fields id` |
| Saturation `0/N novel`, `delta 100.0%` | Set `round` + `novel` when recording; mark re-recorded atoms `metadata.backfill=true` (excluded, printed as `backfill atoms: N (excluded)`); `run measure --material --write-state` |
| 200+ add-link calls, no body action | `K action add-link --root P --batch links.jsonl` (one verify, all or nothing); hand-write the body, then `K index` |
| Many arXiv/W3C papers count as one publisher | Pass `publisher=<authors' organisation>` per source; R6 |
| No browser | Record NOT RUN; look.md "Without a browser" |

## Files

| File | Read when |
| --- | --- |
| [rules.md](rules.md), [concepts.md](concepts.md), [look.md](look.md) | before building, planning, and checking |
| [references/ontology-first-workflow.md](references/ontology-first-workflow.md), [references/ukmc-v2-summary.md](references/ukmc-v2-summary.md) | commands in order; the contract in one page |
| [ATTRIBUTION.md](ATTRIBUTION.md) | sources and licences |
