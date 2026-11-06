# build.py spec

[../build.py](../build.py) drives the real CLI (`pack init`, `run record`, `action ...`, `index`) from one JSON file.
A source `body` is written to a temporary HTML file outside the pack and frozen with
`ingest --freeze <url> --from-file <tmp.html>`, so `captures.jsonl` records origin `from-file`. That step does not
fetch. Use it for fixtures, smoke tests and tiny packs; real research freezes live pages.
Examples: [../examples/tiny-document-pack.json](../examples/tiny-document-pack.json),
[../examples/tiny-entity-pack.json](../examples/tiny-entity-pack.json).

| Key | Shape |
| --- | --- |
| `topic`, `run`, `budget`, `researcher` | strings, int; `researcher` is frozen into the run |
| `sources[]` | `{stem, url, body}` frozen through `ingest --freeze --from-file` into `_evidence/<run>/sources/<stem>.txt` and logged in `captures.jsonl` |
| `atoms[]` | `{id, source (stem), statement, quote, claim_type?, confidence?, round?, novel?, metadata?}` |
| `claims[]` | `{atom, id?, publisher?, kind?, into?, contradicted_kind?}` -> `promote-claim` |
| `entities[]` | `{id, object_type?, title}` -> `create-object` |
| `documents[]` | `{id, object_type?, title, description, when[], source[] (stems), purpose?, allowed[]?, not_allowed[]?, core[], failure_modes?}`; `core` items are text lines or `{"claim": id}` (anchor + `cites` link) |
| `links[]` | `{source, link_type, target}` -> `add-link` |
| `resolutions[]` | `{claim, resolution}` -> `resolve-contradiction` |
| `state` | `{key: value}` -> `run state set`. `consecutive_low_delta_rounds`, `last_weighted_delta` and `resolved` are not accepted; `run measure --write-state` writes the saturation keys |
| `review` | object written to `_evidence/<run>/review.json` (fixture only; `validate.py` accepts `passed: true`. A real review is `run review`, which re-fetches logged URLs and binds the file to the ledger. The stopping gate does not accept `passed` on its own) |

Order: init, freeze, record, promote, entities, documents, links, resolutions, state, review, index.
Exit 0 prints the pack path; 1 means a CLI step refused (its message is printed); 2 means the product could not run.
The output directory must not exist.
