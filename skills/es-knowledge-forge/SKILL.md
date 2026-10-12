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

This repository stores no topic files. Run commands against `~/Products/jang-knowledge/<domain>/<topic>`.

## 1. Commands

```bash
# Fingerprint a PDF, image, or web URL. A missing pdftotext raises RuntimeError.
python3 -m knowledge_builder.cli ingest <file_or_url>

# Video extracts are written only under --out. A missing ffmpeg raises RuntimeError.
python3 -m knowledge_builder.cli ingest <video> --out <directory>

# Check frontmatter, list-shaped source_attribution, hashes, anchors, and the four headings.
python3 -m knowledge_builder.cli verify ~/Products/jang-knowledge/<domain>/<topic>

# Print a stopping-gate decision from self-reported flags. This mode does not exit 0.
python3 -m knowledge_builder.cli gate --run-id <run_id>

# Check the four headings and an ease:source anchor.
python3 -m knowledge_builder.cli lint <markdown_file>

# Write index.json with the sha256 of each file. Skips _evidence/**.
python3 -m knowledge_builder.cli index --root ~/Products/jang-knowledge/<domain>/<topic>
```

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
