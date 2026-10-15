# Rules

Numbered; each has the statement, the CLI that keeps it (flags are in [contract.txt](contract.txt)),
and when it is rejected. **Home** says who rejects: `validate:<check>` (mechanical, [validate.py](validate.py)),
`tool` (the product CLI refuses or `verify` fails; validate shows it as a `verify:` line),
`look L<n>` ([look.md](look.md)) or `hand-over` (a field in SKILL.md section 4; a reviewer reads it).
`K` below means `python3 -m knowledge_builder.cli`.

## R1. The schema is proposed, then approved by the owner
Keep it: write `ontology.proposal.yaml` + a short rationale next to the pack, ask the owner through
AskUserQuestion, and only then copy it to `ontology.yaml`. Start from `K pack init` (starter ontology).
Rejected when: `ontology.yaml` differs from the starter with no recorded approval, or building began before the answer.
Home: hand-over (`APPROVAL`).

## R2. Freeze every source before quoting it
Keep it: web page `K ingest --freeze <url> --root <pack> --run <run> --stem <kebab-stem>`; a local file is copied
into `_evidence/<run>/sources/` and never edited. The quote comes from that file, not from a summary.
Rejected when: a quote is not in its capture, or a capture's sha256 changed.
Home: validate:verify.

## R3. Every atom carries its round and novelty
Keep it: `K run record --root <pack> --id <run>` with `metadata.round` (integer >= 1), `metadata.novel` (true/false),
`metadata.url` when the frozen file has no `Source-URL:` header. One atom, one quote, one fact.
Rejected when: `run record` answers `invalid atom`.
Home: tool.

## R4. Measure saturation on material atoms, then write it
Keep it: `K run measure --root <pack> --id <run> --material --write-state` after each round.
Rejected when: the gate prints `delta 100.0%` only because `last_weighted_delta` was never written.
Home: hand-over (`GATE`).

## R5. Claims come from the ledger through promote-claim
Keep it: `K action promote-claim --root <pack> --param atom=<id> --param id=<curated-kebab-id>`; corroborate an
existing claim with `--param into=<claim>`; many at once with `--batch file.jsonl` (all or nothing). A local frozen
file with no URL (execution output, authored example) takes `--param kind=first-party`; it never adds to independence. A pack made before this kind existed adds `first-party` to the `source` `kind` values in its own `ontology.yaml` first (the tool refuses otherwise and names the allowed list).
Never hand-write a claim or source file.
Rejected when: a claim names an atom the ledger does not hold, or a quote no longer matches its capture.
Home: validate:verify.

## R6. A publisher is who wrote the page, never the host that serves it
Keep it: for `arxiv.org`, `github.com`, `raw.githubusercontent.com`, `githubusercontent.com`, `web.archive.org`,
`hackmd.io` (and subdomains) pass `--param publisher=<author organisation>`; the tool refuses a hosting host
that is derived from the URL. A Source already made is corrected with
`K action set-source --root <pack> --param source=<source-id> --param publisher=<name>` (and/or `--param kind=<kind>`):
same refusal, and only those two keys change.
Rejected when: a Source's `publisher` is one of those hosts.
Home: validate:hosting-publisher.

## R7. One publisher, one kind
Keep it: pick `official`, `academic`, `vendor`, `practitioner`, `community` or `first-party` once per publisher and pass the same
`--param kind=` every time; a docs site and a blog on one host are two judgments, so choose the dominant one.
Rejected when: one publisher appears under two kinds.
Home: validate:publisher-kind.

## R8. Documents and entities are made by create-object, with the type's own properties
Keep it: `K action create-object --root <pack> --param id=<id> --param object_type=<type> --param title=<t>`
plus the type's declared properties (`--param family=x`); a document adds `domain`, `description` and repeatable
`--param when=` / `--param source=` (one entry each). The tool writes into the type's `folder:` (entities in `entities/`).
Rejected when: a parameter is not declared, a type lives in the wrong folder, or `verify` fails after the edit (rolled back).
Home: tool.

## R9. Every claim a document uses is cited twice: anchor and link
Keep it: the body line `<!-- ease:claim id=<claim> -->` directly under the sentence, and
`K action add-link --root <pack> --param source=<doc> --param link_type=cites --param target=<claim>`.
Anchors and `cites` links must be the same set. Write the body after create-object, before add-link.
Rejected when: a claim is cited by no document, a document cites no claim, or anchors and links differ.
Home: validate:uncited-claims, validate:documents-without-claims, validate:verify.

## R10. Relations are links, and link types are declared
Keep it: `about` (document or claim -> entity), `compares` (comparison -> each compared concept), `depends-on`,
`contradicts`, all through `add-link`. Author the `compares` links; a comparison without them looks complete and is not.
Rejected when: a link type is undeclared, a target is missing, or its type differs from `to`.
Home: tool.

## R11. A contradiction is recorded, then resolved with a reason
Keep it: the CONTRADICTION atom has `metadata.contradicts=<atom id>`; after promoting,
`K action resolve-contradiction --root <pack> --param claim=<id> --param resolution=<why both stand or which wins>`,
or deprecate one side.
Rejected when: a CONTRADICTION claim has no resolution and neither side is deprecated.
Home: validate:contradictions.

## R12. A different runtime reviews the pack
Keep it: the reviewer writes `_evidence/<run>/review.json` with `passed: true`, a `reviewer_runtime` that differs
from the run's `researcher_runtime`, `scope`, `checks`, `findings`. The researcher never writes it.
Rejected when: the file is missing, `passed` is not true, or both runtimes are equal.
Home: validate:review.

## R13. A pack with no target library declares it
Keep it: `K run state set --root <pack> --id <run> --key version_applicability --value not_applicable` and
`--key version_reason --value "<why>"` (without the reason the gate does not pass it).
Rejected when: the gate lists a version deficiency for a concept pack.
Home: hand-over (`GATE`).

## R14. The index is fresh after every hand edit
Keep it: `K index --root <pack>` after editing a document body. Actions rebuild it themselves.
Rejected when: `index.json` hash differs from a file.
Home: validate:index.

## R15. The gate is reported, never forced
Keep it: print the `gate:` line of `pack check` as is. `STOP_SUFFICIENT` needs ledger, sources, saturation and review;
nothing in this skill can grant it.
Rejected when: a hand-over says "sufficient" while the gate says DEEPEN, PAUSE_BUDGET or ABSTAIN_BLOCKED.
Home: hand-over (`GATE`).

## R16. Knowledge lives apart from the tool
Keep it: the pack root is `<project>/knowledge/<topic>/` when the topic has its own project, else
`~/Products/jang-knowledge/<domain>/<topic>/`. This repository stores no topic files.
Rejected when: a pack root is inside the knowledge-builder checkout.
Home: hand-over (`PACK`).

## R17. Check output decides, not memory
Keep it: run `validate.py` and `look.py` after the last edit; quote their real output.
Rejected when: a hand-over claims a check passed without its output from after the final change.
Home: hand-over (`VALIDATE`, `LOOK`).

## R18. An existing UKMC.v1 pack is migrated, never extended in place
Keep it: `K pack migrate --from <legacy> --to <new> --run <id> --plan`, fill every `NEEDS_KIND`, `NEEDS_PUBLISHER`,
`NEEDS_CONTRADICTS` (the reviewer's judgment, never a guess), then `K pack migrate --to <new> --apply <new>/migration-plan.json`.
A new pack starts with `pack init`; `--legacy` only checks a v1 root and builds nothing.
Rejected when: `apply` finds a `NEEDS_*` value, or the legacy root changed after the plan.
Home: tool.
