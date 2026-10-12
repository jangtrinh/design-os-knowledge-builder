VERDICT: BLOCKER

Review pinned to `9bdda6d`; HEAD advanced during review. Gate examples below modify an otherwise passing ledger. Reproductions used in-memory filesystem fixtures; no files were edited.

1. **blocker · `research/run_driver.py:123`, `research/ledger.py:66` — Ledger writes escape the run directory.**  
   **Input:** `<root>/_evidence -> /outside`, then `run init --root <root> --id run-1 --budget 4`. Initialization writes `/outside/run-1/{evidence.jsonl,state.json}`. `run record` follows the same escape; an individual `evidence.jsonl` symlink also redirects appends.  
   **Fix:** Enforce resolved containment for the run directory and every output; reject symlinked output files and use no-follow opens.

2. **blocker · `research/ledger_gate.py:165`, `:172` — Unknown version/probe state certifies sufficiency.**  
   **Input:** Remove `is_target_version_matched`, remove `has_viable_probe_remaining`, or set the latter to `"true"`. Each variant produced **`STOP_SUFFICIENT`, exit 0**. Missing version evidence becomes `True`; missing or incorrectly typed probe status becomes `False`.  
   **Fix:** Require explicit boolean values. Unknown version validity or probe exhaustion must prevent certification.

3. **blocker · `index.py:38` — Index output can overwrite an outside file.**  
   **Input:** `<root>/index.json -> /outside/target.json`, with one valid `note.md`; run `index --root <root>`. It opens the outside target with `"w"` and reports success.  
   **Fix:** Reject symlinked output targets and write through a securely created temporary file inside the root.

4. **major · `research/ledger_gate.py:114` — Source aliases inflate independence.**  
   **Input:** `sources/b.txt -> sources/a.txt`; two atoms cite those names with the same valid digest. The certificate reports **two independent sources**, although there is one physical file, and exits 0.  
   **Fix:** Count canonical file identities, reject aliases, and require resolved sources to remain inside this run’s `sources/` directory.

5. **major · `research/ledger_gate.py:80`, `:178` — Malformed cursor data silently weakens checks.**  
   **Input:** `required_claim_ids=["c1", {"id":"unverified-c2"}]` becomes coverage `1/1`; `last_weighted_delta=-1` or `-Infinity` passes saturation. All produced **`STOP_SUFFICIENT`, exit 0**.  
   **Fix:** Reject malformed required IDs instead of filtering them; require a finite, nonnegative delta.

6. **major · `research/ledger_gate.py:32`, `research/stopping_gate.py:73` — Frozen source minimum is ignored.**  
   **Input:** `minimum_independent_sources=3`, with only two sources. The gate still exits 0 because its threshold remains hardcoded to two.  
   **Fix:** Validate and enforce the minimum recorded in the run’s criteria.

7. **major · `research/run_driver.py:75`, `research/ledger_gate.py:102` — Atom identity and type are unchecked.**  
   **Input:** Give the required atom `run_id="run-other"` or `claim_type="NOT_A_CLAIM"`. Both still count as verified and yield exit 0. An unrecognized contradiction type is likewise omitted from contradiction counting.  
   **Fix:** Validate atom field types, allowed claim types, and run identity during both recording and loading.

8. **major · `research/ledger_gate.py:59` — An outside review file is accepted.**  
   **Input:** `review.json -> /outside/old-review.json`, containing `{"passed":true,"reviewer_runtime":"codex"}`, with researcher `"grok"`. The gate reads that outside verdict and certifies the current run.  
   **Fix:** Reject symlinked reviews and require canonical containment within the current run directory.

9. **major · `verify.py:67` — Removing citations bypasses claim verification.**  
   **Input:** Keep valid frontmatter, source hashes and headings, remove every anchor, and add an unsupported sentence. `verify --claims` reports **`anchors: 0`, `failures: 0`, exit 0**.  
   **Fix:** Require claim citations in claims mode and report uncited content as unchecked; zero checked claims must not imply a successful claim check.

10. **major · `verify.py:22`, `:87` — Malformed attributes truncate quotes into matching prefixes.**  
    **Input:** Source contains `He said "no".`; anchor contains `quote="He said "yes"."`. The parser extracts only `He said `, which matches, so verification exits 0. Duplicate `quote` attributes also silently overwrite earlier values.  
    **Fix:** Parse the complete attribute grammar; reject unconsumed text, malformed quoting and duplicate attributes.

11. **major · `verify.py:109`, `:149` — Structural validation skips invalid types and accepts fake headings.**  
    **Input:** `id: []` and `trust_tier: []` pass because validation only checks string values. Placing all four heading strings inside an HTML comment also passes with no actual H2 sections.  
    **Fix:** Require string types for ID/tier and inspect actual body headings outside comments and fenced code.

12. **major · `verify.py:75`, `index.py:60` — Markdown symlinks escape the scanned root.**  
    **Input:** `<root>/note.md -> /outside/note.md`, with otherwise valid content. Both verification and indexing consume the outside document and report success. Citation containment checks do not protect the document itself.  
    **Fix:** Validate canonical containment for every discovered document; reject escaping or unreadable entries explicitly.

13. **minor · `tests/test_stopping_gate.py:50`, `tests/test_claims.py:287` — Acceptance tests can pass vacuously.**  
    **Input:** Disable each source/execution/contradiction/version/counterevidence guard in memory: its corresponding scenario test still passes because review/probe conditions independently force `DEEPEN`. Removing the no-probe conjunction leaves **all 16 stopping-gate tests passing**. The live-root test also accepts zero verified files.  
    **Fix:** Start each negative test from a fully passing fixture and invalidate one condition; assert file/anchor counts in live acceptance tests.

The requested test command exited **1** because the read-only sandbox blocked fixture creation. The commit-pinned suite contained **56 tests, 34 environment errors**; it was not green.

VERDICT: 3 blockers, 9 majors
VERDICT: BLOCKER

Review pinned to `9bdda6d`; HEAD advanced during review. Gate examples below modify an otherwise passing ledger. Reproductions used in-memory filesystem fixtures; no files were edited.

1. **blocker · `research/run_driver.py:123`, `research/ledger.py:66` — Ledger writes escape the run directory.**  
   **Input:** `<root>/_evidence -> /outside`, then `run init --root <root> --id run-1 --budget 4`. Initialization writes `/outside/run-1/{evidence.jsonl,state.json}`. `run record` follows the same escape; an individual `evidence.jsonl` symlink also redirects appends.  
   **Fix:** Enforce resolved containment for the run directory and every output; reject symlinked output files and use no-follow opens.

2. **blocker · `research/ledger_gate.py:165`, `:172` — Unknown version/probe state certifies sufficiency.**  
   **Input:** Remove `is_target_version_matched`, remove `has_viable_probe_remaining`, or set the latter to `"true"`. Each variant produced **`STOP_SUFFICIENT`, exit 0**. Missing version evidence becomes `True`; missing or incorrectly typed probe status becomes `False`.  
   **Fix:** Require explicit boolean values. Unknown version validity or probe exhaustion must prevent certification.

3. **blocker · `index.py:38` — Index output can overwrite an outside file.**  
   **Input:** `<root>/index.json -> /outside/target.json`, with one valid `note.md`; run `index --root <root>`. It opens the outside target with `"w"` and reports success.  
   **Fix:** Reject symlinked output targets and write through a securely created temporary file inside the root.

4. **major · `research/ledger_gate.py:114` — Source aliases inflate independence.**  
   **Input:** `sources/b.txt -> sources/a.txt`; two atoms cite those names with the same valid digest. The certificate reports **two independent sources**, although there is one physical file, and exits 0.  
   **Fix:** Count canonical file identities, reject aliases, and require resolved sources to remain inside this run’s `sources/` directory.

5. **major · `research/ledger_gate.py:80`, `:178` — Malformed cursor data silently weakens checks.**  
   **Input:** `required_claim_ids=["c1", {"id":"unverified-c2"}]` becomes coverage `1/1`; `last_weighted_delta=-1` or `-Infinity` passes saturation. All produced **`STOP_SUFFICIENT`, exit 0**.  
   **Fix:** Reject malformed required IDs instead of filtering them; require a finite, nonnegative delta.

6. **major · `research/ledger_gate.py:32`, `research/stopping_gate.py:73` — Frozen source minimum is ignored.**  
   **Input:** `minimum_independent_sources=3`, with only two sources. The gate still exits 0 because its threshold remains hardcoded to two.  
   **Fix:** Validate and enforce the minimum recorded in the run’s criteria.

7. **major · `research/run_driver.py:75`, `research/ledger_gate.py:102` — Atom identity and type are unchecked.**  
   **Input:** Give the required atom `run_id="run-other"` or `claim_type="NOT_A_CLAIM"`. Both still count as verified and yield exit 0. An unrecognized contradiction type is likewise omitted from contradiction counting.  
   **Fix:** Validate atom field types, allowed claim types, and run identity during both recording and loading.

8. **major · `research/ledger_gate.py:59` — An outside review file is accepted.**  
   **Input:** `review.json -> /outside/old-review.json`, containing `{"passed":true,"reviewer_runtime":"codex"}`, with researcher `"grok"`. The gate reads that outside verdict and certifies the current run.  
   **Fix:** Reject symlinked reviews and require canonical containment within the current run directory.

9. **major · `verify.py:67` — Removing citations bypasses claim verification.**  
   **Input:** Keep valid frontmatter, source hashes and headings, remove every anchor, and add an unsupported sentence. `verify --claims` reports **`anchors: 0`, `failures: 0`, exit 0**.  
   **Fix:** Require claim citations in claims mode and report uncited content as unchecked; zero checked claims must not imply a successful claim check.

10. **major · `verify.py:22`, `:87` — Malformed attributes truncate quotes into matching prefixes.**  
    **Input:** Source contains `He said "no".`; anchor contains `quote="He said "yes"."`. The parser extracts only `He said `, which matches, so verification exits 0. Duplicate `quote` attributes also silently overwrite earlier values.  
    **Fix:** Parse the complete attribute grammar; reject unconsumed text, malformed quoting and duplicate attributes.

11. **major · `verify.py:109`, `:149` — Structural validation skips invalid types and accepts fake headings.**  
    **Input:** `id: []` and `trust_tier: []` pass because validation only checks string values. Placing all four heading strings inside an HTML comment also passes with no actual H2 sections.  
    **Fix:** Require string types for ID/tier and inspect actual body headings outside comments and fenced code.

12. **major · `verify.py:75`, `index.py:60` — Markdown symlinks escape the scanned root.**  
    **Input:** `<root>/note.md -> /outside/note.md`, with otherwise valid content. Both verification and indexing consume the outside document and report success. Citation containment checks do not protect the document itself.  
    **Fix:** Validate canonical containment for every discovered document; reject escaping or unreadable entries explicitly.

13. **minor · `tests/test_stopping_gate.py:50`, `tests/test_claims.py:287` — Acceptance tests can pass vacuously.**  
    **Input:** Disable each source/execution/contradiction/version/counterevidence guard in memory: its corresponding scenario test still passes because review/probe conditions independently force `DEEPEN`. Removing the no-probe conjunction leaves **all 16 stopping-gate tests passing**. The live-root test also accepts zero verified files.  
    **Fix:** Start each negative test from a fully passing fixture and invalidate one condition; assert file/anchor counts in live acceptance tests.

The requested test command exited **1** because the read-only sandbox blocked fixture creation. The commit-pinned suite contained **56 tests, 34 environment errors**; it was not green.

VERDICT: 3 blockers, 9 majors
