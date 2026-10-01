---
name: es:knowledge-forge
description: >
  Universal Multimodal Knowledge Pipeline & Auto-Research Engine.
  Ingests PDF, Video, Image, Audio, and Web into structured Universal Knowledge
  Master Contract (UKMC.v1) Markdown with cryptographic provenance tracking,
  epistemic stopping gates, and multi-perspective audit.
argument-hint: "[ingest <file> | research <topic> | gate <run_id> | lint <file> | index]"
---

# es:knowledge-forge — Universal Multimodal Knowledge & Auto-Research Engine

Governs the lifecycle of knowledge creation, validation, and curation across the Products workspace.

## 1. Commands

```bash
# Ingest any media format (PDF, Video MP4, Diagram image, Web URL)
python3 -m knowledge_builder.cli ingest <file_or_url>

# Run Auto-Research loop with Google Search & GitHub repo inspection
python3 -m knowledge_builder.cli research "<topic>" --github

# Evaluate Stopping Condition (STOP_SUFFICIENT, DEEPEN, PAUSE_BUDGET, ABSTAIN_BLOCKED)
python3 -m knowledge_builder.cli gate --run-id <run_id>

# Lint Markdown against UKMC.v1 standards
python3 -m knowledge_builder.cli lint <markdown_file>

# Compile machine-readable index.json
python3 -m knowledge_builder.cli index --dir ./knowledge
```

## 2. Universal Knowledge Master Contract (UKMC.v1)

Every knowledge file under `knowledge/**` MUST follow the schema:
- **Frontmatter**: `id`, `title`, `domain`, `description`, `when`, `trust_tier`, `source_attribution` (URI + SHA256).
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

## 4. 5-Perspective Council Audit

Prior to graduation, findings are evaluated under 5 lenses:
- **Builder**: Runnable code proof.
- **Red-Team**: Failure modes, race conditions, edge cases.
- **Architect**: KISS/YAGNI/DRY and license safety (quarantine GPL/AGPL).
- **Auditor**: Resource and token overhead benchmarks.
- **Operator**: Observability and debugging ergonomics.
