# DESIGN:OS Knowledge Builder (`design-os-knowledge-builder`)

**Deterministic multimodal knowledge compiler with `UKMC.v1` schema enforcement, SHA-256 provenance, and a 6-validator epistemic gate.**

Compile web documentation, PDFs, codebases, and videos into hallucination-free, token-budgeted knowledge packs (`SKILL.md` + `knowledge/**/*.md`) ready for Claude Code, Codex, Gemini CLI, and Antigravity.

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

Raw RAG chunks and scraped markdown files pollute agent context windows with unverified claims, missing provenance, and prompt-injection risks. **`design-os-knowledge-builder`** compiles raw sources into structured `UKMC.v1` knowledge graphs guarded by a 6-validator epistemic gate.

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
python3 scripts/verify-ukmc.py
```

### 2. Ask in plain English

Open your project in your AI coding agent and describe what you need:

> "Compile these technical RFCs into a UKMC.v1 knowledge pack with SHA-256 source attribution and failure-mode checklists."

> "Audit our knowledge/ directory with the 6-validator epistemic gate and fix any missing frontmatter or untrusted quarantine flags."

> "Generate a progressive-disclosure SKILL.md router and llms.txt index for our domain knowledge base."

### 3. Verify your setup

```bash
python3 scripts/self_check.py
```

---

## What it makes

Every deliverable produced by `design-os-knowledge-builder` is backed by a deterministic verification gate rather than freehand AI guesswork.

<p align="center">
  <img src="assets/cover.png" alt="DESIGN:OS Knowledge Builder Output Specimen" width="840"><br>
  <sub>Prompt: <code>"Compile these technical RFCs into a UKMC.v1 knowledge pack with SHA-256 source attribution and failure-mode checklists."</code></sub>
</p>

| Deliverable / Mode | Best for | Output Format | Verification Gate |
| :--- | :--- | :--- | :--- |
| **UKMC.v1 Knowledge Nodes** | Codifying domain standards with cryptographic source attribution | `Markdown + YAML Frontmatter + Mermaid` | `6-validator epistemic gate PASS` |
| **Agent Skill Routers** | Packaging domain knowledge into portable `skills/<slug>/SKILL.md` bundles | `Progressive-disclosure Skill Pack` | `python3 scripts/self_check.py` |
| **GEO & LLM Indexes** | Publishing machine-readable `llms.txt` and knowledge catalogs | `llms.txt + JSON manifest` | `Zero broken local links` |

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

**Generate & Scaffold**

```text
"Compile these technical RFCs into a UKMC.v1 knowledge pack with SHA-256 source attribution and failure-mode checklists."
```

**Audit & Verify**

```text
"Audit our knowledge/ directory with the 6-validator epistemic gate and fix any missing frontmatter or untrusted quarantine flags."
```

**Export & Automate**

```text
"Generate a progressive-disclosure SKILL.md router and llms.txt index for our domain knowledge base."
```

---

## Commands & Diagnostics

| Command | Environment | What it does |
| :--- | :--- | :--- |
| `/doctor` | Claude Code / Codex | Read-only diagnostic check of installed skill paths, plugin manifests, and runtime prerequisites |
| `python3 scripts/self_check.py` | Terminal / CI | Deterministic offline verification of manifests, skill contracts, and governance files |
| `python3 scripts/verify-ukmc.py` | Terminal / CI | Run the 6-validator UKMC.v1 epistemic gate across all compiled knowledge nodes |

---

## How it works

1. **Intent Routing** — Your AI agent matches your request against `skills/es-knowledge-forge/SKILL.md` frontmatter triggers.
2. **Progressive Context Loading** — Only the entry-point `SKILL.md` router loads initially; detailed recipes and scripts load on demand.
3. **Deterministic Execution** — Domain scripts and contracts execute locally with reproducible inputs and outputs.
4. **Gate Verification** — `scripts/self_check.py` and domain verifiers (`python3 scripts/verify-ukmc.py`) validate the artifact before completion.
5. **Zero-Telemetry Delivery** — Verified files are written directly to your workspace with zero external network calls.

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
│ python3 scripts/verify-ukmc.py
│ Deterministic build & contract enforcement    │
└───────────┬───────────────────────────────────┘
            │ verifies
            ▼
┌───────────────────────────────────────────────┐
│ python3 scripts/self_check.py + /doctor       │
│ Zero-telemetry local verification gate        │
└───────────────────────────────────────────────┘
```

### What loads when

`design-os-knowledge-builder` uses progressive context disclosure so your agent's context window stays fast and focused:

| File | Loaded when |
| :--- | :--- |
| `skills/es-knowledge-forge/SKILL.md` | Always (~100–150 lines) — routing rules, triggers, and execution workflow |
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
│       └── SKILL.md                # Canonical agent skill entrypoint
├── commands/
│   └── doctor.md                   # /doctor diagnostic slash command
├── prompts/
│   └── doctor.md                   # Codex diagnostic prompt mirror
├── scripts/
│   └── self_check.py               # Deterministic repository & skill self-check
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
- `python3 scripts/verify-ukmc.py` passes with zero contract or test regressions.
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
