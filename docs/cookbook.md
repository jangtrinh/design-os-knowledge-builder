# `design-os-knowledge-builder` Prompt & CLI Cookbook

Copy-paste recipes for **DESIGN:OS Knowledge Builder** (`skills/es-knowledge-forge/SKILL.md`).

---

## 1. Build

> "Build an ontology-first knowledge pack on <topic>: freeze the sources, promote claims, cite them from a document, then run the stopping gate."

## 2. Check

> "Check this knowledge pack: run verify --claims and pack check, and list the claims no document cites."

## 3. Extend

> "Add a claim to this pack from a verified evidence atom and cite it in the concept document."

---

## 4. CLI & Diagnostic Commands

```bash
# Offline self-check of manifests, governance files and the skill
python3 scripts/self_check.py

# Check a pack: quotes against frozen sources, then the stopping gate
python3 -m knowledge_builder.cli verify --claims <pack-root>
python3 -m knowledge_builder.cli pack check --root <pack-root>

# The skill's rejection checks and the human-readable look sheet
python3 skills/es-knowledge-forge/validate.py --root <pack-root>
python3 skills/es-knowledge-forge/look.py --root <pack-root> --sheet /absolute/look-sheet.png
```
