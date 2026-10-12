# Plan — honest knowledge pipeline (P0 + P1 + P2)

Source spec: `review-grok-4.7.md` §4 (owner approved ALL on 2026-10-12). Owner rulings that bind every phase:
- The tool never stores topic knowledge; it runs against an external root (first one: `~/Products/jang-knowledge`).
- Stdlib only at runtime (drop the unused `pydantic`). No PyYAML, no embeddings, no LLM calls inside the package.
- The researcher cannot certify its own independent review.

Roles: implementer = Grok `grok-4.7-build-fast` via `grok-run implement` (escalate once to `grok-4.7`);
reviewer = codex (never Grok); controller (Claude) reruns `python3 -m unittest discover tests` + the phase acceptance
after every phase, reads the diff, and commits. Each phase: write the failing test(s) FIRST, run them and paste the red
output, then implement until green, then run the full suite.

| # | Phase | Spec § | Effort | Status |
|---|---|---|---|---|
| 1 | Fail-closed gate: review default false, AND stop rule, honest certificate, exit codes 0/2/3/4/1 | P0.1 | S | done (pending controller) |
| 2 | `verify <root>`: frontmatter schema, list `source_attribution`, repo-relative uris, file exists, sha256, anchors, 4 headings | P0.2 | M | done (pending controller) |
| 3 | `index --root` required, refuse root inside package, `--exclude` default `_evidence/**`, real sha256, id from frontmatter | P0.3 | S | done (pending controller) |
| 4 | Docs tell the truth (skill/README/contract doc) + ingest never invents content | P0.4 + P0.5 | S | todo |
| 5 | `run init/record/status` ledger driver (relative uris only, fsync) | P1.1 | M | todo |
| 6 | `gate --root --run-id` reads the ledger; integer flags only under `--self-report` (never exit 0) | P1.2 | M | todo |
| 7 | Claim-vs-source: `quote=` on anchors and atoms, `verify --claims` | P1.3 | M | todo |
| 8 | `review.json` with reviewer_runtime != researcher_runtime required for STOP_SUFFICIENT | P1.4 | S | todo |
| 9 | Emitter writes list-shaped `source_attribution`; council becomes a gap report; drop pydantic | P1.5 | S | todo |
| 10 | P2: ledger file lock + fsync; optional `entailment_notes` in review.json (data only); optional extractor extras that raise when deps are missing | P2 | M | todo |

Acceptance for the whole plan:
- `python3 -m unittest discover tests` green; every phase added tests that were red before its change.
- A bare `gate` no longer prints `STOP_SUFFICIENT` or exits 0.
- `verify` passes on `~/Products/jang-knowledge` (structure) and fails on a flipped hash.
- `index --root ~/Products/jang-knowledge` writes real hashes and no `_evidence/` rows.
- Independent codex review with no unresolved blocker.
