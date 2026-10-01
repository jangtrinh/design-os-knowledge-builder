"""Universal Knowledge Master Contract (UKMC.v1) data structures and validation."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any
import hashlib
import json
import re


class ModalityType(str, Enum):
    PDF = "pdf"
    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"
    WEB = "web"
    MARKDOWN = "markdown"


class TrustTier(str, Enum):
    VERIFIED = "verified"
    COMMUNITY_REFERENCE = "community_reference"
    DRAFT = "draft"


@dataclass
class SourceAttribution:
    uri: str
    modality: ModalityType
    sha256: str
    captured_at: str
    license_or_origin: Optional[str] = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "modality": self.modality.value,
            "sha256": self.sha256,
            "captured_at": self.captured_at,
            "license_or_origin": self.license_or_origin,
        }


@dataclass
class KnowledgeMetadata:
    id: str
    title: str
    domain: str
    description: str
    when: List[str]
    trust_tier: TrustTier = TrustTier.DRAFT
    version: str = "1.0.0"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


    def validate(self) -> List[str]:
        errors = []
        if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", self.id):
            errors.append(f"Invalid id '{self.id}': must be lowercase alphanumeric with hyphens (kebab-case).")
        if not self.title.strip():
            errors.append("Title cannot be empty.")
        if not self.description.strip():
            errors.append("Description cannot be empty.")
        if not self.when or len(self.when) == 0:
            errors.append("'when' routing tags must contain at least one tag.")
        return errors


@dataclass
class UniversalKnowledgeUnit:
    metadata: KnowledgeMetadata
    source: SourceAttribution
    purpose: str
    when_to_use: List[str]
    when_not_to_use: List[str]
    content: str
    failure_modes: List[str]
    mental_model: Optional[str] = None
    is_external_untrusted: bool = False

    def validate(self) -> List[str]:
        errors = self.metadata.validate()
        if not self.purpose.strip():
            errors.append("Mandatory section 'Purpose' is missing or empty.")
        if not self.when_to_use:
            errors.append("Mandatory section 'When to Use' must contain at least one rule.")
        if not self.when_not_to_use:
            errors.append("Mandatory section 'When NOT to Use' must contain at least one boundary.")
        if not self.content.strip():
            errors.append("Core knowledge content cannot be empty.")
        if not self.failure_modes or len(self.failure_modes) == 0:
            errors.append("Mandatory section 'Failure Modes' must contain at least one known failure mode.")
        return errors

    def to_markdown(self) -> str:
        lines = [
            "---",
            f"id: {self.metadata.id}",
            f"title: \"{self.metadata.title}\"",
            f"domain: \"{self.metadata.domain}\"",
            f"description: \"{self.metadata.description}\"",
            f"when: {json.dumps(self.metadata.when)}",
            f"trust_tier: \"{self.metadata.trust_tier.value}\"",
            f"version: \"{self.metadata.version}\"",
            "source_attribution:",
            f"  uri: \"{self.source.uri}\"",
            f"  modality: \"{self.source.modality.value}\"",
            f"  sha256: \"{self.source.sha256}\"",
            f"  captured_at: \"{self.source.captured_at}\"",
            f"  license: \"{self.source.license_or_origin}\"",
            f"quarantine:",
            f"  is_external_untrusted: {str(self.is_external_untrusted).lower()}",
            "---",
            "",
            f"# {self.metadata.title}",
            "",
            "## Purpose",
            self.purpose,
            "",
        ]

        if self.mental_model:
            lines.extend([
                "## Mental Model",
                self.mental_model,
                "",
            ])

        lines.extend([
            "## When to Use / When NOT",
            "### ALLOWED (When to Use)",
            *[f"- {item}" for item in self.when_to_use],
            "",
            "### NOT ALLOWED (When NOT to Use)",
            *[f"- {item}" for item in self.when_not_to_use],
            "",
            "## Core Knowledge Content",
            f'<!-- ease:source ref="{self.source.uri}" sha256="{self.source.sha256}" captured="{self.source.captured_at}" -->',
            self.content,
            "",
            "## Failure Modes (Mandatory)",
            *[f"1. **{mode.split(':')[0]}**: {mode.split(':', 1)[1].strip() if ':' in mode else mode}" for mode in self.failure_modes],
            "",
        ])

        return "\n".join(lines)
