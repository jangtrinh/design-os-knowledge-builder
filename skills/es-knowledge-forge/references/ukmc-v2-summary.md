# UKMC.v2 summary

Source of truth: `docs/master-contract-ukmc.md` in the knowledge-builder repo. This file is a router-sized summary;
on conflict the contract and [../contract.txt](../contract.txt) win.

## What a pack is

A knowledge root (never inside the tool repo) with `ontology.yaml` (v2) beside markdown objects. Layers:

| Layer | Holds | Checked by |
| --- | --- | --- |
| Evidence | `_evidence/<run>/{state.json,evidence.jsonl,sources/,review.json}` | `run` commands, gate |
| Sources | `sources/<id>.md`: `url`, `kind`, `publisher`, `captures[{evidence_uri,sha256,fetched}]` | `verify` |
| Claims | `claims/<id>.md`: `statement`, `claim_type`, `confidence`, `atom_ids`, `evidence[{atom,run,source,evidence_uri,quote}]`, `supported-by` link | `verify --claims` |
| Documents | root-level `.md` of a `sourced-document` type, four H2 sections, `cites` links, `ease:claim` anchors | `verify --claims` |
| Entities | `entities/<id>.md` (or any type with `folder:`) | `verify` |
| Log | `_actions/actions.jsonl`: one line per accepted action (rejected ones leave none) | `action` |

## Document frontmatter and sections (UKMC.v1, still required)

`id`, `title`, `domain`, `description` (one actionable sentence), `when` (list), `trust_tier`, `version`,
`source_attribution` (list of `{uri, sha256}`, `uri` repo-relative), plus v2 `object_type`, `status`
(experimental, active, deprecated; deprecated needs `superseded_by`), `link_types` (list of `{link_type, target_id}`).
Sections in order: `## Purpose` (1-2 sentences), `## When to Use / When NOT` (ALLOWED / NOT ALLOWED),
`## Core Knowledge Content` (every external fact anchored), `## Failure Modes (Mandatory)`.

## Anchors

`<!-- ease:claim id=<claim-id> -->` directly under the sentence it supports; the set of anchor ids equals the `cites` links.
A block starting `Derived:`, `Decision:` or `Observed:` is not an external fact. A quote containing `"` is written with
single quotes; a quote with both quote characters is a malformed anchor. Legacy packs use `<!-- ease:source ... -->`.

## Stopping gate

| State | Meaning |
| --- | --- |
| `STOP_SUFFICIENT` | required claims verified, >= 2 independent publishers, execution proof, saturation (<= 2% delta over 3 rounds), valid independent review |
| `DEEPEN` | missing claims, single publisher, version drift, untested failure modes, unresolved contradiction, or no review |
| `PAUSE_BUDGET` | budget used up before the evidence is complete; never reported as sufficient |
| `ABSTAIN_BLOCKED` | blocked (paywall, anti-scraping) with no viable fallback |

`gate` with `--self-report` or without `--root` cannot exit 0. The council gap report (`run_council_audit`) lists gaps
(no FAILURE_MODE atom, no BENCHMARK atom, `verified_by_code` atom without `metadata.command`) and returns no pass bit.

## Legacy commands (UKMC.v1 roots without `ontology.yaml`)

`ingest <file|url>` fingerprints PDF/image/web (video needs `--out`); `verify <root> [--claims]`; `lint <file>`;
`index --root`; `gate --root R --run-id RUN`. A missing `pdftotext` or `ffmpeg` raises an error and never fills in text.
