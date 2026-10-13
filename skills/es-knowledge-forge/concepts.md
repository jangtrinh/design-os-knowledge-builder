# Concepts: from a topic to one buildable pack

A request becomes a pack only when each line below can be answered. If one cannot, ask the owner (AskUserQuestion)
or pick the narrower topic. Judgment lives here; [validate.py](validate.py) only rejects facts.

## 1. Turn the request into a concept

| Ask | Answer must be |
| --- | --- |
| Question the pack answers | one sentence an agent could be asked ("which constraint layer for X?") |
| Documents | 1 to 8 modules, each one question; names kebab-case |
| Object types | document types (`concept`, `guide`, `comparison`, `decision-record`) plus any entity type |
| Entities | the things documents are *about* (tools, standards, products); each gets one entity object |
| Sources | at least 2 independent publishers per document claim that matters; first-party runs count as practitioner |
| Required claims | ids the stopping gate must see verified (`pack init --require`) |
| Target library | named version, or `not_applicable` with a reason (R13) |
| Owner | who approves the schema and who may review (a different runtime, R12) |

## 2. Schema proposal

Start from the starter ontology (`pack init` writes it). Change it only for a reason the pack needs. Write the change as
`ontology.proposal.yaml` next to the pack with a rationale block:

```yaml
# ontology.proposal.yaml: copy to ontology.yaml only after the owner approves
object_types:
  architecture:                 # entity type for the compared tools
    folder: entities
    properties:
      - {name: family, type: enum, values: [operational-platform, semantic-web, property-graph]}
link_types:
  - {link_type: about, from: [sourced-document, claim], to: architecture, cardinality: many-to-many}
rationale:
  - architecture: compared tools are things, not documents; each needs an id other documents link to
  - family enum: owner filters comparisons by family
```

State what each addition costs: a new type needs a folder rule and links; a new property needs a value for every object.
Prefer an enum to free text when the owner will filter by it.

## 3. Weak concepts (rewrite or refuse)

| Weak | Why | Better |
| --- | --- | --- |
| "Everything about X" | no question, no stop | name the decision the pack serves |
| One document citing 40 claims | a reviewer cannot read it | split by question |
| Entity type for every noun | links nobody follows | entities only where two documents share the thing |
| Claims restating a source's summary | not a quote-backed fact | quote the sentence, one fact per claim |
| Sources that are all one publisher | independence is 1 | add a second publisher or say so in the hand-over |
| A schema grown to fit one document | the next topic breaks it | keep the starter, add only what two documents need |

## 4. Order of work

Schema proposal → approval → `pack init` → freeze + record (rounds) → measure → promote → documents + entities →
links → contradictions → review → state → validate + look. Details and commands: [references/ontology-first-workflow.md](references/ontology-first-workflow.md).
