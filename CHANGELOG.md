# Changelog (`design-os-knowledge-builder`)

All notable changes to `design-os-knowledge-builder` are documented in this file.

## [Unreleased]

### Changed
- Ontology is the default: `verify`, `index`, `query`, `action`, `pack` and `gate --root` refuse a root without `ontology.yaml`; `--legacy` restores the UKMC.v1 behaviour.

### Added
- `pack migrate --plan` / `--apply`: turn an existing UKMC.v1 pack into an ontology-first pack (captures copied byte-for-byte, claims promoted, bodies ported, `cites` links added); the legacy root is never written.

## [1.0.0] - 2026-10-14

### Added
- Standardized **AI-Ready Repository Delivery Package** (`.claude-plugin`, `.codex-plugin`, `.agents/plugins`, `.factory-plugin`).
- Added `/doctor` diagnostic command (`commands/doctor.md`, `prompts/doctor.md`) and offline `scripts/self_check.py`.
- Added 12-Section Editorial `README.md`, `PRIVACY.md`, `docs/cookbook.md`, and 13-engine `DESIGN:OS` ecosystem cross-links.
