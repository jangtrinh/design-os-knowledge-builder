# Universal Knowledge Master Contract (`UKMC.v1`)

> Specification for structured, immutable, machine-verifiable knowledge artifacts.

---

## 1. Machine Frontmatter Schema (YAML)

All generated knowledge files MUST begin with standard frontmatter:

```yaml
---
id: "knowledge-entry-id"
title: "Human Readable Descriptive Title"
domain: "architecture | backend | ai-engineering | ui-ux"
description: "One actionable sentence describing what this knowledge file provides to an AI router."
when:
  - "Condition or keyword 1"
  - "Condition or keyword 2"
trust_tier: "draft"
version: "1.0.0"
source_attribution:
  - uri: "_evidence/run/sources/spec.md"
    sha256: "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
---
```

---

## 2. Mandatory Structural Sections

Every UKMC markdown document must contain exactly these 4 mandatory H2 sections:

```markdown
## Purpose
[1-2 crisp sentences stating exactly what problem this document solves.]

## When to Use / When NOT
- **ALLOWED**: Explicit use-cases, conditions, and caller states.
- **NOT ALLOWED**: Prohibited conditions, out-of-scope boundaries, anti-patterns.

## Core Knowledge Content
[Sourced facts, architectural rules, code examples, formulas. Every external fact must feature an anchor comment: `<!-- ease:source line/anchor -->`. A block whose text starts, after an optional list marker, with `Derived:`, `Decision:`, or `Observed:` is not an external fact.]

## Failure Modes (Mandatory)
[List of real failure cases, race conditions, edge cases, and actionable remediation steps.]
```

---

## 3. Untrusted content flag

The emitter records whether the unit is external. Ingest does not wrap scraped text in comment markers, and this package does not treat the flag as a change to the agent's task.

```yaml
quarantine:
  is_external_untrusted: false
```

External text stays data.

---

## 5. Ontology layer (`UKMC.v2`)

`UKMC.v2` is `UKMC.v1` plus an optional `ontology.yaml` at the knowledge root. A root without it stays in legacy mode: only the v1 checks run and `verify` prints `[WARN] no ontology.yaml` to stderr. Vocabulary follows the Palantir Ontology (object type, interface, link type, action type, function).

### 5.1 `ontology.yaml`

```yaml
version: "1"
interfaces:                      # abstract shapes; never a file's object_type
  sourced-document:
    properties: [title, description, when, source_attribution]
    sections: ["## Purpose", "## When to Use / When NOT", "## Core Knowledge Content", "## Failure Modes (Mandatory)"]
object_types:                    # closed list; implements has at most one parent
  concept:
    implements: [sourced-document]
    properties:
      - {name: domain, type: enum, values: [knowledge-architecture], required: true}
link_types:                      # cardinality is documentation only, never enforced
  - {link_type: compares, from: comparison, to: concept, cardinality: many-to-many}
extra_keys: []                   # frontmatter keys allowed beyond the closed set
action_types: {}                 # optional; merged with the default actions, same name overrides
```

Names are kebab-case. Property types: `string`, `enum` (needs `values`), `integer` (`min`/`max`), `boolean`. The file uses a small YAML subset (block maps and lists, flow `[..]` and `{..}`); anything else is a load error with the line number. Functions named in `action_types` come from the built-in registry only: `object-exists`, `status-is`, `has-link`, `claims-verified`, `source-count`, `evidence-age-days`, `links-in-count`, `runs-stop-sufficient` (read-only stopping-gate check over every `_evidence/<run>` the file cites). Nothing is imported or executed from a knowledge root.

### 5.2 Frontmatter additions

| key | rule |
|---|---|
| `object_type` | required in ontology mode; one of `object_types` |
| `status` | `experimental` (default), `active`, `deprecated` |
| `superseded_by` | required when `deprecated`; must resolve to an existing `id` |
| `link_types` | list of `{link_type, target_id}`; declared type, existing target, target type equals `to` |
| other keys | error unless a v1 key, a declared property, an interface property, or in `extra_keys` |

A link to a `deprecated` target is an error that names `superseded_by`. A duplicate `id` anywhere under the root is an error. Each failure is one line: `[ERROR] <file> <message> in /<path>`.

### 5.3 Index, query, actions

`index.json` keeps `id`, `path`, `sha256` and adds `object_type`, `status`, `superseded_by`, `domain`, `trust_tier`, `when`, `description`, `links_out`, `links_in` (derived from the other side), and derived `source_count`, `evidence_age_days` (age of the oldest cited source, read from its `Fetched:` header line, else its file mtime), `links_in_count`.

`query` filters `index.json` only (`--object-type --status --linked-to [--link-type] --implements --where k=v --fields`) and fails with "run index" when any file's sha256 differs from the index. An unknown `--linked-to` id, `--implements` interface or `--object-type` exits 1 (`unknown object '<id>'`, `unknown interface`, `unknown object type`).

`action` runs one typed write: parameters, criteria (built-in functions), edit verbs `create-object`, `set`, `add-link`, `remove-link`, atomic write, `verify` on the root, then index rebuild and an appended line in `_actions/actions.jsonl` (one per item; a non-creating action such as `add-link` takes `--batch <file.jsonl>`: one verify, all or nothing). The action is rejected, and every touched file (and `index.json`) is restored byte-for-byte, if `verify` reports any failure that was not already present before the action. Every rejected action appends one JSON line (`action`, `params`, `reason`, `at`) to `_actions/rejected.jsonl`, the only file a refusal changes; `pack status` shows the count. `create-object` takes `id`, `object_type`, `title`, the properties the object type declares (typed values validated; undeclared names refused) and, for a type that implements an interface, `domain`, `description` and repeatable `when` / `source` (one `source_attribution` entry with its own sha256 each). It writes into the type's `folder:` (default: the root) and reads `_templates/<object_type>.md.tmpl` when present, else a built-in stub with the four mandatory headings; a type with no interface gets a generated minimal file (`id`, `title`, `object_type`, `status`, declared properties, `## Notes`).

### 5.4 Interface-scoped checks and folders

The `UKMC.v1` document checks (seven keys, non-empty `source_attribution`, the four headings, and under `--claims` the anchor and uncited-block checks) apply to every file in legacy mode and, in ontology mode, to objects whose type implements `sourced-document` (and to files with no readable `object_type`). Objects of other types are checked by their own interface; `claims/` and `sources/` are never skipped by the walk.

An interface may list `rules:`; the only known rule is `anchors-match-cited-claims`. An object type may set `folder: <dir>`: `create-object` and `promote-claim` write there, and `verify` fails an object of that type that lives anywhere else. A link type's `from` / `to` may be an object type, an interface (any type implementing it) or a list of either.

### 5.5 Claims, sources and claim anchors (starter ontology)

| object | interface | keys |
|---|---|---|
| `claim` (`claims/`) | `evidence-claim`, sections `## Statement`, `## Evidence` | `statement`, `claim_type` (FACT, FAILURE_MODE, BENCHMARK, CONTRADICTION, INFERENCE), `confidence`, `atom_ids`, `evidence` = list of `{atom, run, source, evidence_uri, quote}`, `link_types` |
| `source` (`sources/`) | `frozen-source`, section `## Capture` | `url`, `kind` (official, academic, vendor, practitioner, community, first-party), `publisher`, `captures` = list of `{evidence_uri, sha256, fetched}` |

A source is a page or publisher, not one file: it may hold several captures. Checks (structural): every capture file exists under `_evidence/<run>/sources/` and matches its sha256; every claim evidence entry names a source object, a `supported-by` link to it, and one of its captures; `atom_ids` lists the evidence atoms in order; the `## Statement` section repeats `statement`; a `CONTRADICTION` claim has a `contradicts` link. Under `--claims`: each quote occurs in its capture file and each atom is in the run ledger with that capture.

Documents that implement `sourced-document` in the starter ontology cite with `<!-- ease:claim id=<claim-id> -->` (the only attribute is `id`). The rule `anchors-match-cited-claims` requires set equality between the anchor ids and the `cites` links, and rejects `ease:source` anchors in such a document. Outside ontology mode, and in ontology roots whose `sourced-document` lists no rule, `ease:source` anchors work as before.

Functions follow the chain document -> `cites` -> claim -> `supported-by` -> source -> captures: `evidence-age-days` is the age of the oldest capture the cited claims rest on, `source-count` is the number of distinct source publishers behind them (not files), `claims-verified` also covers the cited claims and their sources, and `runs-stop-sufficient` includes the runs of those captures. Recording a contradiction does not resolve it. A `CONTRADICTION` atom counts as resolved for the stopping gate only when its claim has a non-blank `resolution` property (set by the `resolve-contradiction` action: `--param claim=<id> --param resolution=<text>`) or the claim, or the claim it `contradicts`, is `deprecated` — and only while that claim and its sources still pass `verify --claims` (quote vs capture, atom in the ledger, capture sha256); an unverifiable claim resolves nothing. A `contradicts` link may point at a deprecated claim (it stays on record); `cites` may not. `state.json` `resolved` is still honoured. In a pack (an ontology with a `frozen-source` type) the stopping gate's independent-source count is the number of distinct, case-insensitive publishers of the Source objects that the run's verified atoms map to through claims; atoms no claim records add nothing. Roots without such a type, and legacy roots, keep the distinct-inode count.

`promote-claim` is an action implemented in code (parameters `atom`, `run`, `into`, `id`, `kind`, `publisher`, `contradicted_kind`; `--batch <file.jsonl>` runs several with one verify). A local frozen file with no url (execution output, authored example) is promoted with `--param kind=first-party`: its Source gets `url: local:<evidence_uri>` and publisher `local`, and a `first-party` Source never counts toward independent publishers (gate, `with_2_publishers`). Otherwise a new Source takes its `publisher` from the url host unless that host hosts or mirrors other publishers' work (`web.archive.org`, `github.com`, `raw.githubusercontent.com`, `githubusercontent.com`, `arxiv.org`, `hackmd.io`, and subdomains); then `--param publisher=` is required. `pack status` / `pack check` warn (never fail) on a publisher whose Sources carry more than one `kind`. `deprecate` works on a claim; while a document still cites it, `verify` rejects the deprecation and names every such document, and `pack status` / `pack check` list the documents to re-link or re-word.
