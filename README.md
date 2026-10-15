# DESIGN:OS Knowledge Builder (`design-os-knowledge-builder`)

**Ontology-first knowledge packs: claims with verifiable sources, and a ledger-backed stopping gate.**

Freeze web pages and documents as sources, promote evidence into claims that quote them, and let `verify` check every quote against the frozen file. An agent skill (`skills/es-knowledge-forge/`) teaches Claude Code, Codex, Gemini CLI, and Antigravity the workflow.

<p align="center">
  <img src="assets/cover.png" alt="DESIGN:OS Knowledge Builder — 2:1 Axonometric Technical Architecture" width="840">
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-202020?style=flat-square&labelColor=202020&color=444444" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/Claude_Code_%C2%B7_Codex_%C2%B7_Gemini_%C2%B7_Antigravity-skill-202020?style=flat-square&labelColor=202020&color=444444" alt="Compatible agents">
  <a href="commands/doctor.md"><img src="https://img.shields.io/badge/diagnostics-%2Fdoctor-202020?style=flat-square&labelColor=202020&color=444444" alt="Doctor command"></a>
  <a href="https://jangtrinh.github.io/design-os-knowledge-builder/"><img src="https://img.shields.io/badge/live_docs-GitHub_Pages-202020?style=flat-square&labelColor=202020&color=444444" alt="Live GitHub Pages"></a>
  <a href="https://buymeacoffee.com/jangtrinh"><img src="https://img.shields.io/badge/Buy_Me_a_Coffee-FFDD00?style=flat-square&logo=buy-me-a-coffee&logoColor=black" alt="Buy Me a Coffee"></a>
</p>

<p align="center">
  <a href="#quickstart">Quickstart</a> · <a href="#what-it-makes">What it makes</a> · <a href="#installation">Install</a> · <a href="#how-it-works">How it works</a> · <a href="#commands--diagnostics">Commands</a> · <a href="#quality-bar--limitations">Limits</a>
</p>

---

## Why this exists

Raw RAG chunks and scraped markdown files pollute agent context windows with unverified claims, missing provenance, and prompt-injection risks. **`design-os-knowledge-builder`** compiles raw sources into structured knowledge packs (`UKMC.v2`, with `UKMC.v1` still supported) where a claim is only as good as the quote and hash that back it, and where a research run stops only when its ledger says it is enough. This repository stores no topic files. Packs live in an external knowledge root you choose (`<knowledge-root>/<domain>/<topic>`), apart from the tool.

| Dimension | Generic AI / Manual Workflow | DESIGN:OS Knowledge Builder (`DESIGN:OS`) |
| :--- | :--- | :--- |
| **Provenance & Trust** | Unattributed markdown scrapes with zero hash verification | Mandatory `source_attribution` (`uri`, `sha256`, `license`, `trust_tier`) on every node |
| **Prompt-Injection Safety** | External web text mixed directly into system instructions | Explicit `quarantine.is_external_untrusted` isolation and sanitization |
| **Failure Prevention** | Happy-path notes that omit edge cases | Mandatory `## When to Use / When NOT` and `>= 5` concrete `## Failure Modes` per node |
| **Context Efficiency** | Monolithic dumps that blow the 200k context window | Progressive disclosure (`SKILL.md` router -> domain index -> leaf node) |
| **Privacy & Telemetry** | Opaque cloud telemetry or unverified third-party APIs | **Zero telemetry** — 100% local execution ([`PRIVACY.md`](PRIVACY.md) audited) |

---

## Quickstart

### 1. Install the plugin or CLI

**In Claude Code:**

```text
/plugin marketplace add jangtrinh/design-os-knowledge-builder
/plugin install design-os-knowledge-builder@design-os-knowledge-builder
```

**Or from your terminal (Codex, Gemini CLI, Antigravity, OpenCode, or standalone CLI):**

```bash
git clone https://github.com/jangtrinh/design-os-knowledge-builder.git
cd design-os-knowledge-builder
pip install -e .
python3 -m knowledge_builder.cli --help
```

### 2. Ask in plain English

Open your project in your AI coding agent and describe what you need:

> "Build an ontology-first knowledge pack on <topic>: freeze the sources, promote claims, cite them from a document, then run the stopping gate."

> "Check this knowledge pack: run `verify --claims` and `pack check`, and list the claims no document cites."

> "Add a claim to this pack from a verified evidence atom and cite it in the concept document."

### 3. Verify your setup

```bash
python3 scripts/self_check.py
```

---

## What it makes

Every pack is checked by deterministic commands (`verify`, `pack check`, `gate`) rather than by an agent's say-so.

| Deliverable | Best for | Output | Check |
| :--- | :--- | :--- | :--- |
| **Ontology-first pack** | Domain knowledge where every claim must quote a frozen source | `ontology.yaml`, `claims/`, `sources/`, documents, `_evidence/<run>/` | `pack check` (`verify --claims` + stopping gate) |
| **Index and object sets** | Letting an agent query a pack instead of re-reading it | `index.json`, `query` results | `index` refuses a stale index |
| **Agent skill** | Teaching an agent to build and check packs | `skills/es-knowledge-forge/` | `python3 scripts/self_check.py` |

---

## Installation

Choose the setup that matches your AI coding agent. Every option installs the same canonical skill (`skills/es-knowledge-forge/SKILL.md`) and `/doctor` diagnostic suite.

### Claude Code

Run these two commands inside Claude Code:

```text
/plugin marketplace add jangtrinh/design-os-knowledge-builder
/plugin install design-os-knowledge-builder@design-os-knowledge-builder
```

### OpenAI Codex

Install to your personal Codex skills directory:

```bash
git clone https://github.com/jangtrinh/design-os-knowledge-builder.git /tmp/design-os-knowledge-builder
mkdir -p ~/.codex/skills/es-knowledge-forge ~/.codex/prompts
cp -R /tmp/design-os-knowledge-builder/skills/es-knowledge-forge/* ~/.codex/skills/es-knowledge-forge/
cp /tmp/design-os-knowledge-builder/prompts/doctor.md ~/.codex/prompts/es-knowledge-forge-doctor.md
rm -rf /tmp/design-os-knowledge-builder
```

### Gemini CLI & Google Antigravity

```bash
git clone https://github.com/jangtrinh/design-os-knowledge-builder.git /tmp/design-os-knowledge-builder
mkdir -p ~/.gemini/skills/es-knowledge-forge
cp -R /tmp/design-os-knowledge-builder/skills/es-knowledge-forge/* ~/.gemini/skills/es-knowledge-forge/
rm -rf /tmp/design-os-knowledge-builder
```

### OpenCode, Cursor, Windsurf & Other Agent Harnesses

```bash
git clone https://github.com/jangtrinh/design-os-knowledge-builder.git /tmp/design-os-knowledge-builder
mkdir -p ~/.agents/skills/es-knowledge-forge
cp -R /tmp/design-os-knowledge-builder/skills/es-knowledge-forge/* ~/.agents/skills/es-knowledge-forge/
rm -rf /tmp/design-os-knowledge-builder
```

The skill is a plain folder: `SKILL.md` routes, `rules.md`, `concepts.md` and `look.md` hold the judgment, and `build.py`, `validate.py` and `look.py` do the mechanics with the Python standard library only. They call the `knowledge_builder` tool, so either keep a checkout next to the skill, pass `--repo-root <checkout>`, or run `pip install -e .` from the checkout. A copied skill is a snapshot: re-copy it after you update the repository.

```bash
python3 skills/es-knowledge-forge/build.py --spec skills/es-knowledge-forge/examples/tiny-entity-pack.json --output-dir /absolute/new-pack
python3 skills/es-knowledge-forge/validate.py --root /absolute/new-pack          # exit 0 ok, 1 reject, 2 could not run
python3 skills/es-knowledge-forge/look.py --root /absolute/new-pack --sheet /absolute/look-sheet.png   # needs Chrome or Chromium
python3 scripts/generate-skill-contract.py --check                                # the skill's CLI contract is current
```

CI runs the full test suite, including the skill tests, on Python 3.10 and 3.12.

<details>
<summary>Verify or uninstall</summary>

**Verify installation:**

```bash
python3 scripts/self_check.py
```

Or run `/doctor` inside Claude Code / Codex to inspect installed skill paths, plugin manifests, and gate health.

**Uninstall:**

```bash
rm -rf ~/.claude/skills/es-knowledge-forge ~/.codex/skills/es-knowledge-forge ~/.gemini/skills/es-knowledge-forge ~/.agents/skills/es-knowledge-forge
```

</details>

---

## Usage & Prompt Cookbook

Once installed, `skills/es-knowledge-forge/SKILL.md` activates automatically when your prompt matches its domain triggers. Browse [`docs/cookbook.md`](docs/cookbook.md) for copy-paste prompt recipes.

**Build**

```text
"Build an ontology-first knowledge pack on <topic>: freeze the sources, promote claims, cite them from a document, then run the stopping gate."
```

**Check**

```text
"Check this knowledge pack: run verify --claims and pack check, and list the claims no document cites."
```

**Extend**

```text
"Add a claim to this pack from a verified evidence atom and cite it in the concept document."
```

---

## Commands & Diagnostics

| Command | Environment | What it does |
| :--- | :--- | :--- |
| `/doctor` | Claude Code / Codex | Read-only diagnostic check of installed skill paths, plugin manifests, and runtime prerequisites |
| `python3 scripts/self_check.py` | Terminal / CI | Offline check of manifests, governance files and that a skill exists |
| `python3 -m knowledge_builder.cli verify --claims <pack-root>` | Terminal / CI | Check metadata, anchors and every quote against the frozen capture |
| `python3 -m knowledge_builder.cli pack check --root <pack-root>` | Terminal / CI | Exit 0 only when `verify --claims` passes; prints the stopping-gate decision |
| `python3 skills/es-knowledge-forge/validate.py --root <pack-root>` | Terminal / CI | The skill's rejection checks (uncited claims, hosting-host publishers, unresolved contradictions, stale index) |
| `python3 -m pytest -q` | Terminal / CI | Full test suite, including the skill's shape, contract, example and look tests |

The CLI is `python3 -m knowledge_builder.cli <command>`; the examples below write `kb` for it. Every command is listed with its flags in `skills/es-knowledge-forge/contract.txt` (generated by `scripts/generate-skill-contract.py`).

### Ingest, verify, lint, index
```bash
kb ingest ./whitepaper.pdf                       # PDF; video and images take --out for their extracts
kb verify <knowledge-root>/<domain>/<topic>      # add --claims to check every quote against the frozen capture
kb lint <knowledge-root>/<domain>/<topic>/note.md
kb index --root <knowledge-root>/<domain>/<topic>
kb gate --run-id run-001 --required 5 --verified 5 --sources 3
```

### Research ledger: `run` and `ingest --freeze`
```bash
# One run = _evidence/<id>/{state.json,evidence.jsonl,sources/}
kb run init --root <knowledge-root> --id <run> --budget 400 --require <claim-id> --researcher <runtime>

# Freeze a web page as plain text into sources/ (identity encoding, gzip decoded, never overwrites).
# Prints the sha256 and the repo-relative path to cite in an atom.
kb ingest --freeze <url> --root <knowledge-root> --run <run> --stem <kebab-case-stem>

# Append one atom from stdin. metadata.round is an integer >= 1; metadata.novel is a boolean.
kb run record --root <knowledge-root> --id <run> < atom.json

# Per-round novelty: delta(r) = novel atoms in r / atoms before r. Round 1 is the baseline.
# --material counts a novel atom only when an ease:source anchor in a module cites its quote.
# Atoms with metadata.backfill=true are excluded from novelty and the denominator (printed as "backfill atoms: N (excluded)").
# Nothing is written unless --write-state is given.
kb run measure --root <knowledge-root> --id <run> --material [--write-state]

# Typed writes to state.json. Settable keys: round, consecutive_low_delta_rounds,
# last_weighted_delta, has_viable_probe_remaining, is_target_version_matched,
# version_applicability (applicable | not_applicable), version_reason, resolved (appends).
kb run state set --root <knowledge-root> --id <run> --key version_applicability --value not_applicable
kb run state set --root <knowledge-root> --id <run> --key version_reason --value "concept pack: no target library"

# The gate reads the ledger. It prints "low-delta rounds N/3" and, for a declared
# not-applicable version, "Version:  not applicable: <reason>".
kb gate --root <knowledge-root> --run-id <run>
```
`version_applicability: not_applicable` passes the version gate only with a non-empty `version_reason`; without it the gate stays at DEEPEN.

### Ontology packs: `pack`, `action`, `query`
A root with an `ontology.yaml` is in ontology mode (`UKMC.v2`); without one the tool behaves as before and prints a legacy-mode warning to stderr. See the `UKMC.v2` section of [docs/master-contract-ukmc.md](docs/master-contract-ukmc.md).
```bash
kb pack init --root <pack-root> --topic "my topic" --run my-run --require some-claim-id   # new or empty root only
kb pack status --root <pack-root>        # one screen of counts (add --json)
kb pack check --root <pack-root>         # exits 0 only when verify --claims passes; prints the gate decision
kb query --root <pack-root> --object-type concept --status active --fields id,links_in_count   # read-only; refuses a stale index
kb action promote-claim --root <pack-root> --param atom=hb-1 --param kind=official
kb action promote-claim --root <pack-root> --param atom=hb-3 --param into=<claim-id> --param kind=academic
kb action promote-claim --root <pack-root> --batch atoms.jsonl     # all or nothing, one verify for the batch
kb action promote-claim --root <pack-root> --param atom=sa-1 --param kind=first-party   # local execution output: no URL, publisher local, never independent
kb action set-source --root <pack-root> --param source=<source-id> --param publisher=Microsoft   # re-attribute a Source: publisher and/or kind
kb action create-object --root <pack-root> --param id=<id> --param object_type=entity --param title="..."
kb action add-link --root <pack-root> --param source=<id> --param link_type=cites --param target=<claim-id>
kb action add-link --root <pack-root> --batch links.jsonl          # many links, one verify, all or nothing
kb action resolve-contradiction --root <pack-root> --param claim=<id> --param resolution="<text>"
```
Default actions: `create-object`, `add-link`, `deprecate`, `promote-trust-tier`, `promote-claim`, `set-source`, `resolve-contradiction`. Actions declared in `ontology.yaml` `action_types` are merged with the defaults; declaring the same name overrides a default. Every action runs under one lock per root, edits atomically, verifies, rolls back on failure, rebuilds the index and appends a line to `_actions/actions.jsonl`; a refused action appends one line to `_actions/rejected.jsonl` instead (`pack status` shows the count).

Rules the tool enforces:
- `set-source` edits only the `publisher` and/or `kind` lines of a `frozen-source` object (kind must be in the type's declared enum; a hosting or mirror host is refused as publisher; a refusal goes to `rejected.jsonl`). Publisher counts, `pack status` `with_2_publishers` and the gate's independence follow at once; publishers compare case-insensitively.
- `promote-claim` refuses an atom whose frozen file hash or quote does not verify, and an atom that is already promoted (the error names the claim). Pass `--param id=<short-kebab-id>` to name the claim; without it the id is the first words of the statement, cut at 60 characters.
- It does not guess a publisher from a hosting or mirror host (`web.archive.org`, `github.com`, `raw.githubusercontent.com`, `githubusercontent.com`, `arxiv.org`, `hackmd.io`, and subdomains): pass `--param publisher=<who published it>`. `pack status` and `pack check` print a `warning:` for a publisher whose sources carry more than one `kind`.
- Promoting a `CONTRADICTION` atom also promotes the atom named in `metadata.contradicts` and links the two with `contradicts`. That records the contradiction; it resolves nothing for the stopping gate. `resolve-contradiction` (or deprecating one side) does, and the claim must still verify.
- `create-object` takes the parameters of the object type it creates: `id`, `object_type`, `title`, every property the type declares (enum, integer and boolean values are checked before anything is written; an undeclared name is refused and the declared ones are listed), and, for a type with an interface, `domain`, `description`, `when` and `source`. The file goes into the type's `folder:`.
- `promote-trust-tier` to `verified` also needs the stopping gate to return STOP_SUFFICIENT for every `_evidence/<run>` the file cites.

### Anchor rule: `ease:claim` must equal `cites`
A document cites a claim with `<!-- ease:claim id=<claim-id> -->` under the block it supports and a `cites` link to that claim. The quote lives only in the claim. Every anchor id must be in the document's `cites` links and every `cites` target must be used by an anchor; `verify --claims` rejects either mismatch.

Other anchor rules checked by `verify --claims`:
- A quote that contains `"` is written with single quotes: `<!-- ease:source uri=... sha256=... quote='He said "go".' -->`. A quote holding both `"` and `'` cannot be written either way; cite a shorter fragment.
- A `Derived:`, `Observed:`, or `Decision:` line directly above a table or code fence (the very next line) exempts that one block. A blank line in between, or the label below the block, does not.

---

## How it works

1. **Intent Routing** — Your AI agent matches your request against `skills/es-knowledge-forge/SKILL.md` frontmatter triggers.
2. **Progressive Context Loading** — Only the entry-point `SKILL.md` router loads initially; `rules.md`, `concepts.md`, `look.md` and `references/` load on demand.
3. **Deterministic Execution** — `build.py` turns a JSON spec into real CLI calls; `ingest --freeze` fetches a URL; `validate.py` and `look.py` use no network.
4. **Gate Verification** — `scripts/self_check.py` and `verify --claims`, `pack check` and the skill's `validate.py` validate the artifact before completion.
5. **Zero-Telemetry Delivery** — Verified files are written to your workspace; no telemetry is sent.

```text
User Prompt / CLI Invocation
            │
            ▼
┌───────────────────────────────────────────────┐
│ skills/es-knowledge-forge/SKILL.md
│ Progressive disclosure router & hard rules    │
└───────────┬───────────────────────────────────┘
            │ loads on demand
            ▼
┌───────────────────────────────────────────────┐
│ build.py -> knowledge_builder CLI             │
│ Frozen sources, claims, links, ontology       │
└───────────┬───────────────────────────────────┘
            │ verifies
            ▼
┌───────────────────────────────────────────────┐
│ validate.py + pack check + stopping gate      │
│ look.py renders the pack for human eyes       │
└───────────────────────────────────────────────┘
```

### What loads when

`design-os-knowledge-builder` uses progressive context disclosure so your agent's context window stays fast and focused:

| File | Loaded when |
| :--- | :--- |
| `skills/es-knowledge-forge/SKILL.md` | Always (under 120 lines) — the procedure and what to open next |
| `skills/es-knowledge-forge/rules.md`, `concepts.md`, `look.md` | While building, checking and reviewing a pack |
| `skills/es-knowledge-forge/contract.txt` | When you need the exact CLI flags (generated, sha256 on its first line) |
| `docs/cookbook.md` | When selecting multi-step prompt recipes or domain patterns |
| `commands/doctor.md` / `prompts/doctor.md` | Only when running `/doctor` diagnostics |
| `llms.txt` | When indexed by AI answer engines, RAG pipelines, or repo crawlers |

---

## File structure

```text
design-os-knowledge-builder/
├── .claude-plugin/
│   ├── plugin.json                 # Claude Code plugin manifest
│   └── marketplace.json            # Claude Code marketplace catalog
├── .codex-plugin/
│   └── plugin.json                 # OpenAI Codex plugin & interface manifest
├── .agents/
│   └── plugins/marketplace.json    # Cross-agent local plugin registry
├── .factory-plugin/
│   ├── plugin.json                 # Factory / Droid plugin manifest
│   └── marketplace.json            # Factory marketplace metadata
├── skills/
│   └── es-knowledge-forge/
│       ├── SKILL.md                # Canonical agent skill entrypoint (router)
│       ├── rules.md  concepts.md  look.md
│       ├── build.py  validate.py  look.py  forge_common.py  look_sheet.py
│       ├── contract.txt            # Generated CLI contract
│       ├── references/             # Ontology-first workflow, UKMC.v2 summary, build spec
│       └── examples/               # Two small packs as build specs
├── commands/
│   └── doctor.md                   # /doctor diagnostic slash command
├── prompts/
│   └── doctor.md                   # Codex diagnostic prompt mirror
├── scripts/
│   ├── self_check.py               # Deterministic repository & skill self-check
│   └── generate-skill-contract.py  # Regenerates skills/es-knowledge-forge/contract.txt (--check)
├── src/knowledge_builder/          # The tool (CLI, verify, index, gate, actions, pack)
├── tests/                          # Tool tests and test_skill_* tests
├── .github/workflows/test.yml      # pytest on Python 3.10 and 3.12, self-check, contract --check
├── docs/
│   ├── cookbook.md                 # Copy-paste prompt recipes by job
│   └── llms.txt                    # GEO / LLM discovery index
├── PRIVACY.md                      # Zero-telemetry & local-first privacy commitment
├── SECURITY.md                     # Vulnerability disclosure & security policy
├── CONTRIBUTING.md                 # Contribution workflow & verification rules
├── CODE_OF_CONDUCT.md              # Contributor Covenant code of conduct
├── CHANGELOG.md                    # Release history
├── llms.txt                        # Root LLM indexing manifest
├── LICENSE                         # MIT License
└── README.md
```

---

## Quality bar & Limitations

### It's working if...

- `python3 scripts/self_check.py` prints `ok: design-os-knowledge-builder self-check passed (es-knowledge-forge)` and exits `0`.
- `python3 -m pytest -q` passes and `python3 scripts/generate-skill-contract.py --check` exits `0`.
- `python3 skills/es-knowledge-forge/validate.py --root <pack-root>` prints `ok` for your pack.
- Your AI coding agent loads `skills/es-knowledge-forge/SKILL.md` automatically when given any prompt from [`docs/cookbook.md`](docs/cookbook.md).
- Network traffic during execution remains zero (guaranteed by [`PRIVACY.md`](PRIVACY.md)).

### When not to use

- Unstructured creative brainstorming or freeform journaling where strict schema gates add unnecessary friction.
- Storing live credentials, secrets, or personally identifiable customer data (PII).
- Replacing a transactional SQL/vector database for millions of real-time user records.

---

## DESIGN:OS Ecosystem

`design-os-knowledge-builder` is one of the 13 open-source engines in the **`DESIGN:OS`** ecosystem:

| Engine | Live Docs | Repository | Layer |
| :--- | :--- | :--- | :--- |
| **DESIGN:OS CLI** | [jangtrinh.github.io/design-os](https://jangtrinh.github.io/design-os/) | [`jangtrinh/design-os`](https://github.com/jangtrinh/design-os) | `cli` |
| **Knowledge Builder** | [jangtrinh.github.io/design-os-knowledge-builder](https://jangtrinh.github.io/design-os-knowledge-builder/) | [`jangtrinh/design-os-knowledge-builder`](https://github.com/jangtrinh/design-os-knowledge-builder) | `compiler` |
| **Figma Plugin & CLI** | [jangtrinh.github.io/design-os-figma-plugin](https://jangtrinh.github.io/design-os-figma-plugin/) | [`jangtrinh/design-os-figma-plugin`](https://github.com/jangtrinh/design-os-figma-plugin) | `plugin` |
| **SVG Animation Engine** | [jangtrinh.github.io/design-os-svg-animation](https://jangtrinh.github.io/design-os-svg-animation/) | [`jangtrinh/design-os-svg-animation`](https://github.com/jangtrinh/design-os-svg-animation) | `engine` |
| **3D Blender Agent** | [jangtrinh.github.io/design-os-3d-blender](https://jangtrinh.github.io/design-os-3d-blender/) | [`jangtrinh/design-os-3d-blender`](https://github.com/jangtrinh/design-os-3d-blender) | `3d / cad` |
| **OPAH ONE Drone** | [jangtrinh.github.io/design-os-drone-showcase](https://jangtrinh.github.io/design-os-drone-showcase/) | [`jangtrinh/design-os-drone-showcase`](https://github.com/jangtrinh/design-os-drone-showcase) | `hardware` |
| **GitHub Pages Engine** | [jangtrinh.github.io/design-os-github-page](https://jangtrinh.github.io/design-os-github-page/) | [`jangtrinh/design-os-github-page`](https://github.com/jangtrinh/design-os-github-page) | `pages` |
| **Apple Design OS** | [jangtrinh.github.io/design-os-apple](https://jangtrinh.github.io/design-os-apple/) | [`jangtrinh/design-os-apple`](https://github.com/jangtrinh/design-os-apple) | `swiftui` |
| **Agent Teacher** | [jangtrinh.github.io/design-os-pedagogy](https://jangtrinh.github.io/design-os-pedagogy/) | [`jangtrinh/design-os-pedagogy`](https://github.com/jangtrinh/design-os-pedagogy) | `pedagogy` |
| **Origami CAD** | [jangtrinh.github.io/design-os-origami](https://jangtrinh.github.io/design-os-origami/) | [`jangtrinh/design-os-origami`](https://github.com/jangtrinh/design-os-origami) | `packaging` |
| **Voice UX Architecture** | [jangtrinh.github.io/design-os-voice-ux](https://jangtrinh.github.io/design-os-voice-ux/) | [`jangtrinh/design-os-voice-ux`](https://github.com/jangtrinh/design-os-voice-ux) | `voice-ai` |
| **Code2Flow** | [jangtrinh.github.io/design-os-code2flow](https://jangtrinh.github.io/design-os-code2flow/) | [`jangtrinh/design-os-code2flow`](https://github.com/jangtrinh/design-os-code2flow) | `ast / audit` |
| **Generative UI** | [jangtrinh.github.io/design-os-generative-ui](https://jangtrinh.github.io/design-os-generative-ui/) | [`jangtrinh/design-os-generative-ui`](https://github.com/jangtrinh/design-os-generative-ui) | `runtime` |

---

## Contributing, Governance & License

- **Contributing**: See [`CONTRIBUTING.md`](CONTRIBUTING.md) for pull request guidelines and verification gates (`python3 scripts/self_check.py`).
- **Code of Conduct**: Governed by [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).
- **Security & Privacy**: Zero telemetry — see [`SECURITY.md`](SECURITY.md) and [`PRIVACY.md`](PRIVACY.md).
- **Changelog & LLM Index**: Track releases in [`CHANGELOG.md`](CHANGELOG.md) and machine-readable index in [`llms.txt`](llms.txt).
- **License**: [MIT](LICENSE) © [Jang Trinh](https://github.com/jangtrinh).

---

If `design-os-knowledge-builder` saves you time, a star on GitHub helps other engineers and AI agents find it.

<p align="left">
  <a href="https://buymeacoffee.com/jangtrinh">
    <img src="https://img.shields.io/badge/Buy_Me_a_Coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black" alt="Buy Me a Coffee">
  </a>
</p>
