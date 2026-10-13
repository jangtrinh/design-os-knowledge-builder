"""Actions that ship when ontology.yaml declares no action_types, plus the stub object template."""

STRING, ID, OBJECT = {"type": "string"}, {"type": "id"}, {"type": "object_id"}

DEFAULT_ACTIONS = {
    "create-object": {
        "parameters": {
            "id": ID, "object_type": STRING, "domain": STRING, "title": STRING,
            "description": STRING, "when": STRING, "source": STRING,
        },
        "criteria": [],
        "edits": [{"create-object": {
            "id": "$id", "object_type": "$object_type",
            "values": {"title": "$title", "domain": "$domain", "description": "$description",
                       "when": "$when", "source": "$source"},
        }}],
    },
    "add-link": {
        "parameters": {"source": OBJECT, "link_type": STRING, "target": OBJECT},
        "criteria": [],
        "edits": [{"add-link": {"object": "source", "link_type": "link_type", "target": "target"}}],
    },
    "deprecate": {
        "parameters": {"target": OBJECT, "replacement": OBJECT},
        "criteria": [
            {"function": "object-exists", "args": ["replacement"]},
            {"function": "status-is", "args": ["target", "active"]},
        ],
        "edits": [
            {"set": {"object": "target", "key": "status", "value": "deprecated"}},
            {"set": {"object": "target", "key": "superseded_by", "value": "$replacement"}},
        ],
    },
    "resolve-contradiction": {
        "parameters": {"claim": OBJECT, "resolution": STRING},
        "criteria": [
            {"function": "claim-type-is", "args": ["claim", "CONTRADICTION"]},
            {"function": "non-blank", "args": ["resolution"]},
        ],
        "edits": [{"set": {"object": "claim", "key": "resolution", "value": "$resolution"}}],
    },
    "promote-trust-tier": {
        "parameters": {"target": OBJECT, "tier": STRING},
        "criteria": [
            {"function": "claims-verified", "args": ["target"]},
            {"function": "runs-stop-sufficient", "args": ["target", "tier"]},
        ],
        "edits": [{"set": {"object": "target", "key": "trust_tier", "value": "$tier"}}],
    },
}

DEFAULT_TEMPLATE = '''---
id: "{{id}}"
title: "{{title}}"
object_type: "{{object_type}}"
domain: "{{domain}}"
description: "{{description}}"
when:
  - "{{when}}"
trust_tier: "draft"
version: "1.0.0"
source_attribution:
  - uri: "{{source}}"
    sha256: "{{source_sha256}}"
---

## Purpose

Pending.

## When to Use / When NOT

Pending.

## Core Knowledge Content

Pending.

## Failure Modes (Mandatory)

Pending.
'''
