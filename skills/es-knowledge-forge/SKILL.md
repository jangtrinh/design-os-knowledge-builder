---
name: es:knowledge-forge
description: >
  Universal Multimodal Knowledge Pipeline.
  Ingests PDF, Video, Image, and Web into structured Universal Knowledge
  Master Contract (UKMC.v1) Markdown with cryptographic provenance tracking,
  epistemic stopping gates, and a council gap report.
argument-hint: "[ingest <file> | verify <root> | gate | lint <file> | index --root]"
---

# es:knowledge-forge — Universal Multimodal Knowledge Pipeline

This repository stores no topic files. The knowledge root is a separate repository you choose. Run commands against `<knowledge-root>/<domain>/<topic>`.

## 1. Commands

```bash
# Fingerprint a PDF, image, or web URL. A missing pdftotext raises RuntimeError.
python3 -m knowledge_builder.cli ingest <file_or_url>

# Video extracts are written only under --out. A missing ffmpeg raises RuntimeError.
python3 -m knowledge_builder.cli ingest <video> --out <directory>

# Check frontmatter, list-shaped source_attribution, hashes, anchors, and the four headings.
python3 -m knowledge_builder.cli verify <knowledge-root>/<domain>/<topic>

# Print a stopping-gate decision from self-reported flags. This mode does not exit 0.
python3 -m knowledge_builder.cli gate --run-id <run_id>

# Check the four headings and an ease:source anchor.
python3 -m knowledge_builder.cli lint <markdown_file>

# Write index.json with the sha256 of each file. Skips _evidence/**.
python3 -m knowledge_builder.cli index --root <knowledge-root>/<domain>/<topic>

# Freeze a web page as plain text into a run's sources/ (never overwrites). Prints sha256 + path.
python3 -m knowledge_builder.cli ingest --freeze <url> --root <knowledge-root> --run <run> --stem <kebab-case-stem>

# Per-round novelty from the ledger. --material counts only novel atoms whose quote an anchor cites.
# Writes nothing unless --write-state.
python3 -m knowledge_builder.cli run measure --root <knowledge-root> --id <run> --material [--write-state]

# Typed state writes: round, consecutive_low_delta_rounds, last_weighted_delta,
# has_viable_probe_remaining, is_target_version_matched, version_applicability, version_reason, resolved.
python3 -m knowledge_builder.cli run state set --root <knowledge-root> --id <run> --key <key> --value <value>
```

Version gate for a pack with no target library: set `version_applicability=not_applicable` and a non-empty `version_reason`; the gate prints the reason. Without the reason it does not pass.

Anchor rules under `verify --claims`: a quote containing `"` uses single quotes (`quote='He said "go".'`); a quote with both quote characters is a malformed anchor. A `Derived:`/`Observed:`/`Decision:` line on the line directly above a table or fence exempts that block.

## 2. Universal Knowledge Master Contract (UKMC.v1)

Every knowledge file under the external root MUST follow the schema:
- **Frontmatter**: `id`, `title`, `domain`, `description`, `when`, `trust_tier`, `version`, and `source_attribution` as a list of `{uri, sha256}`. `uri` is repo-relative.
- **Mandatory Sections**:
  1. `## Purpose`: Exactly 1-2 sentences defining what this file solves.
  2. `## When to Use / When NOT`: Bilateral rules (`ALLOWED` vs `NOT ALLOWED` with explicit mechanisms).
  3. `## Core Knowledge Content`: Sourced facts with `<!-- ease:source ... -->`.
  4. `## Failure Modes (Mandatory)`: Observable failure cases and anti-patterns.

## 3. Epistemic Stopping Gate (4 Termination States)

- `STOP_SUFFICIENT`: 100% required claims verified, $\ge 2$ independent sources, code execution proof, saturation achieved ($\le 2\%$ delta across 3 rounds).
- `DEEPEN`: Missing claims, single-source bias, version drift, or untested failure modes.
- `PAUSE_BUDGET`: Budget exhausted without completing evidence. (Never claim "sufficient").
- `ABSTAIN_BLOCKED`: Blocked by paywall or anti-scraping without viable fallback.

## 4. Council gap report

`run_council_audit` reads evidence atoms and lists gaps. It returns no pass bit, and the stopping gate does not read this report. `STOP_SUFFICIENT` comes from the ledger plus `review.json`, where `reviewer_runtime` differs from `researcher_runtime`.

A gap is one of:

- missing a `FAILURE_MODE` atom
- missing a `BENCHMARK` atom
- a `verified_by_code` atom whose `metadata.command` is missing
