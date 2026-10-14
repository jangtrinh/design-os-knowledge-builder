---
description: Diagnose DESIGN:OS Knowledge Builder installation, plugin manifests, skill files, and local verification gates
allowed-tools: Bash, Read, Glob
---

# `design-os-knowledge-builder` `/doctor` Diagnostics

Run a read-only diagnostic check of the `design-os-knowledge-builder` installation and repository health. Do **not** modify, create, or delete any files during this check.

## Steps

1. **Run the deterministic self-check script** when inside a `design-os-knowledge-builder` checkout:
   ```bash
   python3 scripts/self_check.py
   ```
2. **Check installed skill locations** across active agent harnesses:
   - Claude Code: `~/.claude/skills/es-knowledge-forge/SKILL.md` or `.claude-plugin/marketplace.json`
   - OpenAI Codex: `~/.codex/skills/es-knowledge-forge/SKILL.md` or `.codex-plugin/plugin.json`
   - Gemini CLI / Antigravity: `~/.gemini/skills/es-knowledge-forge/SKILL.md`
   - Cross-agent `.agents`: `~/.agents/skills/es-knowledge-forge/SKILL.md`
3. **Report a concise health table** covering:
   - Manifest integrity (`.claude-plugin`, `.codex-plugin`, `.agents/plugins`, `.factory-plugin`)
   - Canonical skill (`skills/es-knowledge-forge/SKILL.md`)
   - Trust & privacy governance (`PRIVACY.md`, `SECURITY.md`, `LICENSE`)
   - Domain command readiness (`python3 -m knowledge_builder.cli --help` and `python3 scripts/generate-skill-contract.py --check`)
