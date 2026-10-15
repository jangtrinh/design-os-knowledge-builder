# Fixed visual inspection

Run [look.py](look.py) only after [validate.py](validate.py) exits 0. It renders one sheet (1440px wide, desktop
default; responsive checks are SKIPPED unless the owner asks) from `pack status --json` and the links in `index.json`:
gate banner, documents → claims → sources → entities strip, counts table, entities, warnings, per-document table.
Open the PNG and read it; machine items are measured by the script, eye items by you.

| Item | Check | Home |
| --- | --- | --- |
| L1 | Sheet PNG is 1440px wide and at least 10 KB (not blank) | machine, look.py |
| L2 | Objects on the sheet (live pack status) equal the entries of `index.json` | machine, look.py |
| L3 | Claims reached through `cites` links equal claims minus uncited | machine, look.py |
| L4 | Sheet HTML makes no external request | machine, look.py |
| L5 | Numbers and text are legible: nothing clipped, overlapped or cut mid-word | eyes |
| L6 | The strip reads like the pack you built: document, claim, source and entity counts are plausible | eyes |
| L7 | Entities listed are the ones you meant, each with the documents that are about it | eyes |
| L8 | Warnings and the gate banner say what the validate output and your hand-over say | eyes |

Right: open the saved sheet, tick L5 to L8, quote the machine lines for L1 to L4.
Wrong: call exit 0 "looks good", or grade a thumbnail you did not open.

| Symptom | Action | Never |
| --- | --- | --- |
| L2 or L3 fails | `K index --root <pack>`, rerun validate, then look | edit look.py to match |
| Sheet clipped or empty | rerun with `--sheet` on a fresh path; check the browser | report L5 from the PNG's byte size |
| Strip counts surprise you | read the document table; a document citing nothing is the usual cause | trust the strip over validate |
| Entities missing | `about` links are absent (R10) | add entities without links |

## Without a browser

`look.py` exits 2 (`runtime: could not run: no browser ...`). Install nothing into the skill or the cwd; use
`--browser <path>` or `CHROME_BIN` if one exists elsewhere. Otherwise report exactly:

```text
LOOK: NOT RUN — no browser (Chrome/Chromium) available.
```

A missing browser does not satisfy the visual gate: do not substitute validate output, an old screenshot or another pack's sheet.
