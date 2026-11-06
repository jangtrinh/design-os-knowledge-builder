# Contributing to `design-os-knowledge-builder`

Thank you for contributing to **DESIGN:OS Knowledge Builder** (`DESIGN:OS`).

## Verification Gate Before Submitting a PR

Every pull request must pass the local self-check and repository test suite before merge:

```bash
python3 scripts/self_check.py
PYTHONPATH=src python3 -m unittest discover -s tests -t . -q
python3 scripts/generate-skill-contract.py --check
```

## Guidelines

1. **Zero Telemetry**: Do not add analytics, phone-home, or unpinned runtime dependencies. The only network call is `ingest --freeze` without `--from-file`, which fetches the URL the user named.
2. **Progressive Context Disclosure**: Keep `skills/es-knowledge-forge/SKILL.md` concise (~150 lines) and place detailed recipes in `docs/cookbook.md`.
3. **Conventional Commits**: Use `feat:`, `fix:`, `docs:`, or `chore:` commit prefixes.
