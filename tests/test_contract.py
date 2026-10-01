"""Test Universal Knowledge Master Contract (UKMC.v1) data structures."""

import unittest
from knowledge_builder.contract import (
    UniversalKnowledgeUnit,
    KnowledgeMetadata,
    SourceAttribution,
    ModalityType,
    TrustTier,
)


class TestContractValidation(unittest.TestCase):

    def test_valid_contract_to_markdown(self):
        meta = KnowledgeMetadata(
            id="event-sourcing-patterns",
            title="Event Sourcing Patterns",
            domain="architecture",
            description="Production guidelines for event-driven systems.",
            when=["event-sourcing", "cqrs", "event-store"],
            trust_tier=TrustTier.VERIFIED,
        )
        source = SourceAttribution(
            uri="file://docs/event-sourcing.pdf",
            modality=ModalityType.PDF,
            sha256="abc1234567890",
            captured_at="2026-10",
        )
        unit = UniversalKnowledgeUnit(
            metadata=meta,
            source=source,
            purpose="Standardize aggregate root boundary design.",
            when_to_use=["When auditability is strict"],
            when_not_to_use=["When CRUD suffices"],
            content="Maintain append-only stream of events.",
            failure_modes=["Dual write without transactional outbox"],
        )

        errors = unit.validate()
        self.assertEqual(len(errors), 0)

        md = unit.to_markdown()
        self.assertIn("id: event-sourcing-patterns", md)
        self.assertIn("## Purpose", md)
        self.assertIn("## When to Use / When NOT", md)
        self.assertIn("## Failure Modes (Mandatory)", md)
        self.assertIn('<!-- ease:source ref="file://docs/event-sourcing.pdf"', md)

    def test_invalid_contract_catches_missing_failure_modes(self):
        meta = KnowledgeMetadata(
            id="bad-entry",
            title="Bad Entry",
            domain="test",
            description="Testing missing sections.",
            when=["test"],
        )
        source = SourceAttribution(
            uri="https://example.com",
            modality=ModalityType.WEB,
            sha256="dummy",
            captured_at="2026-10",
        )
        unit = UniversalKnowledgeUnit(
            metadata=meta,
            source=source,
            purpose="Testing validation errors",
            when_to_use=["Testing"],
            when_not_to_use=["Testing"],
            content="Some content",
            failure_modes=[],  # Empty failure modes!
        )

        errors = unit.validate()
        self.assertIn("Mandatory section 'Failure Modes' must contain at least one known failure mode.", errors)


if __name__ == "__main__":
    unittest.main()
