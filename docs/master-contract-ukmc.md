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

`query` filters `index.json` only (`--object-type --status --linked-to [--link-type] --implements --where k=v --fields`) and fails with "run index" when any file's sha256 differs from the index.

`action` runs one typed write: parameters, criteria (built-in functions), edit verbs `create-object`, `set`, `add-link`, `remove-link`, atomic write, `verify` on the root, then index rebuild and an appended line in `_actions/actions.jsonl`. The action is rejected, and every touched file (and `index.json`) is restored byte-for-byte, if `verify` reports any failure that was not already present before the action. `create-object` reads `_templates/<object_type>.md.tmpl` when present, else a built-in stub with the four mandatory headings.

