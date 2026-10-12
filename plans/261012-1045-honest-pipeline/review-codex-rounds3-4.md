# Codex re-review after rounds 3-4 (2026-10-12)

Reviewer: codex exec -s read-only. Implementer of the reviewed code: Grok. Scope B = containment, ledger, gates, index, video.

## Accepted risks (controller ruling)
Remaining MINOR items #1, #3/#14 and video #9 need a concurrent writer swapping paths during a run. Threat model: local CLI on the owner's own knowledge repo, single writer. Accepted, not fixed; revisit if the builder ever runs on shared or untrusted roots.

## Review B output
VERDICT: CONCERNS

1. **#1 PARTIAL · MINOR · `research/ledger.py:152,169,196`.** Reused-ledger writes reject an already-swapped `_evidence`. A concurrent swap immediately before append still writes outside; reused reads follow swapped ancestors without revalidation. Python repro: swap `_evidence` inside a patched `open_append_nofollow`, then `record_atom(atom)` → outside append succeeds.

2. **#3 PARTIAL · MINOR · `index.py:46`, `containment.py:220`.** Existing `index.json` symlinks are rejected. Temporary-file substitution still publishes a symlink; same repro as #14.

3. **#6 FIXED · `research/ledger_gate.py:208`.** Missing source minimum now rejects certification. Repro:
   `PYTHONPATH=src python3 -B -m unittest tests.test_round3_findings.TestRound3Findings.test_f06_missing_minimum_blocks_stop`

4. **#12 FIXED within scope · `index.py:98,107`.** Discovered-file symlink substitution fails; metadata and digest use the same bytes. Repro:
   `PYTHONPATH=src python3 -B -m unittest tests.test_round3_findings.TestRound3Findings.test_f12_markdown_reread_stays_inside_root`

5. **#14 PARTIAL · MINOR · `containment.py:220`.** Directory substitution after opening is fixed. The temporary pathname remains replaceable before publication. Python repro, with `d` a temporary directory:
   ```python
   real = os.replace
   def swap(src, dst, **kw):
       os.unlink(src, dir_fd=kw["src_dir_fd"])
       os.symlink("/etc/hosts", src, dir_fd=kw["src_dir_fd"])
       return real(src, dst, **kw)
   with patch("os.replace", swap):
       atomic_write(d, "index.json", b"SAFE")
   ```
   Result: published `index.json` is a symlink. Requires a concurrent writer.

6. **#15 FIXED · `containment.py:140`, `research/ledger.py:154`.** Repeated short writes complete; zero-progress publication raises. Repro:
   `PYTHONPATH=src python3 -B -m unittest tests.test_round3_findings.TestRound3Findings.test_f15_short_write_is_not_success`

7. **#16 FIXED · `research/stopping_gate.py:84`.** Zero, negative, boolean, string, float and null minima reject. Repro:
   `PYTHONPATH=src python3 -B -m unittest tests.test_round3_findings.TestRound3Findings.test_f16_evaluator_rejects_invalid_minimum_sources`

8. **Probe/version typing FIXED · `research/stopping_gate.py:85`, `research/ledger_gate.py:185,190`.** Missing and malformed values prevent STOP through both paths. Repro:
   `PYTHONPATH=src python3 -B -m unittest tests.test_round4_findings.TestRound4StoppingGate tests.test_review_findings.TestReviewFindings.test_f02_unknown_version_or_probe_state_cannot_stop`

9. **NEW MINOR · `processors/video.py:79`.** Static audio/frame symlinks are rejected. Swapping `output_dir` during the second ffmpeg call redirects frame publication through its ancestor: Python repro patches `_ffmpeg` to rename `output_dir`, symlink its former pathname to an outside directory containing `frames/`, then return a scratch PNG → outside frame written; returned audio path missing.

10. **Verification limit.** Six targeted and ten additional tests passed with an in-memory filesystem; adversarial repros above also ran there. Native filesystem fixtures were blocked by the read-only sandbox. No files edited.

## Review A output (verify.py per-block rule) — fixed in round 5
1. **MAJOR · [verify.py:388](/Users/jangtrinh/orca/workspaces/design-os-knowledge-builder/kb-review-fixes/src/knowledge_builder/verify.py:388)** — One multiline anchor cites two paragraphs because coverage uses whole lines. Python repro Core: `P1\n\n<!-- ease:source uri=LICENSE sha256=<LICENSE hash> quote="MIT License"\n-->P2`. Result: `failures=[]`. Below, `A` means this valid anchor on one line.

2. **MAJOR · [verify.py:282](/Users/jangtrinh/orca/workspaces/design-os-knowledge-builder/kb-review-fixes/src/knowledge_builder/verify.py:282)** — Hidden headings terminate Core checking. Repros: `Supported\nA\n\n    ## Hidden\n\nUnsupported` and `~~~\nA\n## Hidden\n~~~\n\nUnsupported`. Both return `failures=[]`; later visible prose escapes checking.

3. **MAJOR · [verify.py:232](/Users/jangtrinh/orca/workspaces/design-os-knowledge-builder/kb-review-fixes/src/knowledge_builder/verify.py:232)** — HTML comments are stripped inside code fences, corrupting subsequent parsing. Repro: `` ```html\n<!--\n```\nA\n\nUnsupported `` → `failures=[]`. Also, `` ```\n<!-- literal code -->\nDerived: decoy\n``` `` becomes exempt despite its first literal line lacking an exemption label.

4. **MAJOR · [verify.py:399](/Users/jangtrinh/orca/workspaces/design-os-knowledge-builder/kb-review-fixes/src/knowledge_builder/verify.py:399)** — Anchors nested inside another comment count as citations. Repro: `Unsupported\n<!-- outer\nA` → `failures=[]`, although `A` is comment content.

5. **MAJOR · [verify.py:332](/Users/jangtrinh/orca/workspaces/design-os-knowledge-builder/kb-review-fixes/src/knowledge_builder/verify.py:332)** — Tables swallow following list items containing pipes. Repro: `| a | b |\n| --- | --- |\n| 1 | 2 | A\n- Unsupported | claim` → `failures=[]`. The table’s anchor covers the separate list item.

6. **MAJOR · [verify.py:355](/Users/jangtrinh/orca/workspaces/design-os-knowledge-builder/kb-review-fixes/src/knowledge_builder/verify.py:355)** — Blockquoted list items merge into one block. Repro: `> - Unsupported A\n> - Unsupported B\nA` → `failures=[]`; one anchor covers both items.
