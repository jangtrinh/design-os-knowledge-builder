# Ontology-first workflow (proven by the ontology-v2 dogfood, 2026-10-13)

`K` = `python3 -m knowledge_builder.cli`; `P` = the pack root; `R` = the run id. Every step names what it proves and
the closing condition (done only when it holds). Flags: [../contract.txt](../contract.txt). Rules: [../rules.md](../rules.md).

| # | Step | Command | Closing condition |
| --- | --- | --- | --- |
| 1 | Scaffold | `K pack init --root P --topic "<topic>" --run R --researcher <runtime> [--require <claim-id>]...` | `P/ontology.yaml`, `claims/`, `sources/`, `_evidence/R/` exist |
| 2 | Propose schema | write `P/ontology.proposal.yaml` + rationale | file exists; the owner has not answered yet |
| 3 | Owner approval | AskUserQuestion (<= 4 per round, recommended first) | answer recorded; only then copy to `ontology.yaml` |
| 4 | Freeze sources | `K ingest --freeze <url> --root P --run R --stem <stem>`; local files copied into `_evidence/R/sources/` | each frozen file's sha256 printed |
| 5 | Record atoms | `echo '<atom json>' \| K run record --root P --id R` | atom has `round`, `novel`, quote copied from the frozen file |
| 6 | Measure | `K run measure --root P --id R --material --write-state` | `last_weighted_delta` written |
| 7 | Promote | `K action promote-claim --root P --param atom=<id> --param id=<claim-id> [--param publisher=<org>] [--param kind=<kind>]` or `--batch f.jsonl` | claim + source files exist; `--into` for corroboration |
| 8 | Documents, entities | `K action create-object ...` then write the body | file under its type's folder |
| 9 | Cite | body anchor `<!-- ease:claim id=<claim> -->` + `K action add-link ... link_type=cites` | anchors == cites links |
| 10 | Relate | `add-link` with `about` / `compares` / `depends-on` | no declared relation missing |
| 11 | Contradictions | `K action resolve-contradiction --root P --param claim=<id> --param resolution="<reason>"` | none unresolved |
| 12 | Independent review | a different runtime writes `_evidence/R/review.json` | `validate:review` passes |
| 13 | State | `K run state set --root P --id R --key version_applicability --value not_applicable` + `--key version_reason` | gate shows no version deficiency |
| 14 | Check | `K pack check --root P`, `K pack status --root P`, then [../validate.py](../validate.py), [../look.py](../look.py) | exit 0, sheet inspected |

## Migrating an existing UKMC.v1 pack

| # | Step | Command | Closing condition |
| --- | --- | --- | --- |
| M1 | Plan | `K pack migrate --from L --to P --run R --plan` | `P/migration-plan.json` only; legacy root untouched |
| M2 | Fill | edit the plan: every `NEEDS_KIND`, `NEEDS_PUBLISHER`, `NEEDS_CONTRADICTS`; claim ids, object types if wanted | no `NEEDS_` left |
| M3 | Apply | `K pack migrate --to P --apply P/migration-plan.json` | `pack check` exit 0 (it is the command's exit) |
| M4 | Review | steps 12-14 above | a different runtime wrote `review.json` |

Kinds and publishers are the owner's or reviewer's judgment: a hosting host (arxiv, github) never names the publisher.

## Atom shape

```json
{"id":"a1","run_id":"R","claim_type":"FACT","statement":"<one sentence>","source_uri":"_evidence/R/sources/<stem>.txt",
 "source_digest":"<sha256 of that file>","captured_at":"<iso>","confidence":"HIGH","verified_by_code":false,
 "metadata":{"round":1,"novel":true,"url":"<page url, only if the file has no Source-URL header>"},"quote":"<verbatim from the file>"}
```

`claim_type` is FACT, FAILURE_MODE, BENCHMARK, CONTRADICTION or INFERENCE. A CONTRADICTION atom adds
`metadata.contradicts=<other atom id>`. A `verified_by_code` atom needs `metadata.command`.

## Create-object parameters

Always `id`, `object_type`, `title`. A document type (one implementing `sourced-document`) adds `domain`, `description`
and `when` / `source` (repeat the flag for several; `source` is a repo-relative frozen file, its sha256 is computed).
Declared properties of the type are accepted and validated (enum values). Anything else is rejected with the declared list.

## Batches

`promote-claim --batch` takes JSONL, one object per line (`{"atom":"a1","id":"x","publisher":"org"}`); all items succeed
or nothing changes. `add-link` has no batch: loop in the shell, one call per link (about 0.4 s each).

## When to stop

Read the `gate:` line of `pack check`. DEEPEN lists what is missing (saturation, probes, review, version).
Do not edit state to make it pass: measure, review and declare honestly (R15).
