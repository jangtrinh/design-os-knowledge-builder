# Ontology-first workflow (proven by the ontology-v2 dogfood, 2026-10-13)

`K` = `python3 -m knowledge_builder.cli`; `P` = the pack root; `R` = the run id. Every step names what it proves and
the closing condition (done only when it holds). Flags: [../contract.txt](../contract.txt). Rules: [../rules.md](../rules.md).

| # | Step | Command | Closing condition |
| --- | --- | --- | --- |
| 1 | Scaffold | `K pack init --root P --topic "<topic>" --run R --researcher <runtime> [--require <claim-id>]...` | `P/ontology.yaml`, `claims/`, `sources/`, `_evidence/R/` exist |
| 2 | Propose schema | write `P/ontology.proposal.yaml` + rationale | file exists; the owner has not answered yet |
| 3 | Owner approval | AskUserQuestion (<= 4 per round, recommended first) | answer recorded; only then copy to `ontology.yaml` |
| 4 | Freeze sources | `K ingest --freeze <url> [--from-file <saved.html>] --root P --run R --stem <stem>`; local files copied into `_evidence/R/sources/` | each frozen file's sha256 printed |
| 5 | Record atoms | `echo '<atom json>' \| K run record --root P --id R` | atom has `round`, `novel`, quote copied from the frozen file |
| 6 | Promote | `K action promote-claim --root P --param atom=<id> --param id=<claim-id> [--param publisher=<org>] [--param kind=<kind>]` or `--batch f.jsonl` | claim + source files exist; `--into` for corroboration |
| 7 | Documents, entities | `K action create-object ...` then write the body | file under its type's folder |
| 8 | Cite | body anchor `<!-- ease:claim id=<claim> -->` + `K action add-link --root P --param source=<doc> --param link_type=cites --param target=<claim>` or `--batch f.jsonl` | anchors == cites links |
| 9 | Measure | `K run measure --root P --id R --material --write-state` (after citing each round) | `last_weighted_delta` written |
| 10 | Relate | `add-link` with `about` / `compares` / `depends-on` | no declared relation missing |
| 11 | Contradictions | `K action resolve-contradiction --root P --param claim=<id> --param resolution="<reason>"` | none unresolved |
| 12 | Independent review | a different runtime writes `_evidence/R/review.json` | `validate:review` passes |
| 13 | State | `K run state set --root P --id R --key version_applicability --value not_applicable` + `--key version_reason` (and `execution_applicability` + `execution_reason` when no code) | gate shows no version/execution deficiency |
| 14 | Check | `K pack check --root P`, `K pack status --root P`, then [../validate.py](../validate.py), [../look.py](../look.py) | exit 0, sheet inspected |

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

`promote-claim --batch` takes JSONL, one object per line (`{"atom":"a1","id":"x","publisher":"org"}`).
`K action add-link --root P --batch f.jsonl` takes JSONL (`{"source":"<doc>","link_type":"cites","target":"<claim>"}`); one verify runs at the end and all items succeed or nothing changes.

## When to stop

Read the `gate:` line of `pack check`. DEEPEN lists what is missing (saturation, probes, review, version).
Do not edit state to make it pass: measure, review and declare honestly (R15).
