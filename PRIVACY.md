# Privacy Policy (`design-os-knowledge-builder`)

`design-os-knowledge-builder` (`DESIGN:OS Knowledge Builder`) is a local-first, source-available engineering tool and AI agent skill in the **DESIGN:OS** ecosystem.

## Zero Telemetry Guarantee

- **No telemetry**: `design-os-knowledge-builder` does not phone home, collect analytics, or transmit source code, prompts, or generated artifacts to any external server.
- **Fetches only when a command names a URL or asks to recheck**: `ingest --freeze <url>` without `--from-file` fetches that URL and stores the extracted text locally. `run review` re-fetches the URL of every logged capture whose origin is `fetched` or `from-file` and an atom cites, checks quotes against the live page, and does not write `sources/`. `gate --recheck` and `pack check --recheck` fetch those same pages again and do not write `sources/`. They do not re-run execution captures. `ingest --freeze --from-file` and `run exec` do not fetch. Without `--recheck`, `gate` and `pack check` do not fetch.
- **No third-party tracking**: There are no embedded telemetry beacons, crash reporters, or usage trackers in `skills/`, `scripts/`, or plugin manifests.
- **Local files**: All other reads, validations, and builds happen inside your local workspace and under your active AI coding agent's permission model. Those files are writable by whoever runs the tool.
- **Auditable source**: Every script and prompt in this repository is plain-text Markdown, Python, or JavaScript/Swift under the [PolyForm Shield License 1.0.0](LICENSE).

## Contact

For privacy or security questions, see [`SECURITY.md`](SECURITY.md) or open an issue on [`jangtrinh/design-os-knowledge-builder`](https://github.com/jangtrinh/design-os-knowledge-builder).
