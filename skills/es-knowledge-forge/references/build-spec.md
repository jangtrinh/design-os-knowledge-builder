# build.py spec

[../build.py](../build.py) drives the real CLI (`pack init`, `run record`, `action ...`, `index`) from one JSON file,
offline: a source's `body` is written as the frozen capture (what `ingest --freeze` would store). Use it for fixtures,
smoke tests and tiny packs; real research freezes live pages. Examples: [../examples/tiny-document-pack.json](../examples/tiny-document-pack.json),
[../examples/tiny-entity-pack.json](../examples/tiny-entity-pack.json).

| Key | Shape |
| --- | --- |
| `topic`, `run`, `budget`, `researcher` | strings, int; `researcher` is frozen into the run |
| `sources[]` | `{stem, url, body}` written to `_evidence/<run>/sources/<stem>.txt` with a `Source-URL:` header |
| `atoms[]` | `{id, source (stem), statement, quote, claim_type?, confidence?, round?, novel?, metadata?}` |
| `claims[]` | `{atom, id?, publisher?, kind?, into?, contradicted_kind?}` -> `promote-claim` |
| `entities[]` | `{id, object_type?, title}` -> `create-object` |
| `documents[]` | `{id, object_type?, title, description, when[], source[] (stems), purpose?, allowed[]?, not_allowed[]?, core[], failure_modes?}`; `core` items are text lines or `{"claim": id}` (anchor + `cites` link) |
| `links[]` | `{source, link_type, target}` -> `add-link` |
| `resolutions[]` | `{claim, resolution}` -> `resolve-contradiction` |
| `state` | `{key: value}` -> `run state set` |
| `review` | object written to `_evidence/<run>/review.json` (fixture only; a real review is another runtime's work) |

Order: init, freeze, record, promote, entities, documents, links, resolutions, state, review, index.
Exit 0 prints the pack path; 1 means a CLI step refused (its message is printed); 2 means the product could not run.
The output directory must not exist.
