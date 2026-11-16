# Asset provenance

## Clay mark
`design-os-knowledge-builder.webp` (256x256, staircase block) is the official hub mark from `jangtrinh/jangtrinh.github.io`, path `assets/logos/design-os-knowledge-builder.webp` on main, copied as-is. sha256 `d8f62646e3d624dabdf0cc194f3915d71e8989169fbc1eb8b58e2e61c94b14bd`. The hub's `assets/logos/SOURCES.txt` records it as one of the clay marks Jang accepted on 2026-11-02. It is not recoloured.

## Covers, flow diagrams and social preview
Family-matched cards in the same layout as the other DESIGN:OS README refreshes: 1600x720 covers, 1600x1000 flow, 1280x640 social. Be Vietnam Pro (400, 600, 800) with a ui-monospace stack for code, rendered with headless Chrome, then quantised to an indexed palette. Dark #09090b, light #f4f4f5, accent #fca849. Footer: FREE + source-available (PolyForm Shield). `social-preview.png` is not uploaded in repository Settings.

Every number on the cards comes from the code: 10 MiB and 300 s from `src/knowledge_builder/research/run_exec.py`, 6 words and 30 characters from `src/knowledge_builder/quote_rules.py`, the four decisions and the 3-round, 2% saturation rule from `src/knowledge_builder/research/stopping_gate.py`, the six hosting hosts from `src/knowledge_builder/ontology/hosting_hosts.py`, and the seven built-in actions from the generated `skills/es-knowledge-forge/contract.txt`.

## Look sheets
`look-sheet-tiny-entity-pack.png` and `look-sheet-tiny-document-pack.png` are real output of `skills/es-knowledge-forge/look.py`, run on packs built by `build.py` from `skills/es-knowledge-forge/examples/tiny-entity-pack.json` and `tiny-document-pack.json` (look.py printed L1 to L4 ok for both). The palette was reduced to keep the files small. The only edit is a grey bar over the local pack path in each header line (the text after `run tiny-...-261013 ·`), so no machine path is published.
