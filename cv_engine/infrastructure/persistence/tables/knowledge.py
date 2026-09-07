"""Knowledge/facts tables: fact lifecycle audit and the mutation journal."""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from ._helpers import sequence_column
from ._metadata import metadata

fact_events = Table(
    "fact_events",
    metadata,
    Column("id", String, primary_key=True),
    sequence_column("fact_events"),
    Column("fact_id", String, nullable=False),
    Column("source_file", Text, nullable=False),
    Column("event_type", Text, nullable=False),
    Column("from_status", Text),
    Column("to_status", Text, nullable=False),
    Column("application_id", String, ForeignKey("applications.id")),
    Column("claim_id", String),
    Column("reason", Text, nullable=False, server_default=text("''")),
    Column("fact_json", JSONB, nullable=False),
    Column("fact_hash", Text, nullable=False),
    Column("facts_version", Text, nullable=False),
    Column("lifecycle_version", Text, nullable=False),
    Column("created_at", Text, nullable=False),
)
Index("idx_fact_events_fact", fact_events.c.fact_id)

knowledge_mutation_journal = Table(
    "knowledge_mutation_journal",
    metadata,
    Column("id", String, primary_key=True),
    Column("mutation_type", Text, nullable=False),
    Column("state", Text, nullable=False),
    Column("source_reference", Text, nullable=False),
    Column("staged_reference", Text, nullable=False, unique=True),
    Column("old_sha256", Text, nullable=False),
    Column("new_sha256", Text, nullable=False),
    Column("db_mutation_type", Text, nullable=False),
    Column("db_mutation_id", String, nullable=False),
    Column("db_mutation_json", JSONB, nullable=False),
    Column("recovery_strategy", Text, nullable=False),
    Column("prepared_at", Text, nullable=False),
    Column("committed_at", Text),
    Column("quarantined_at", Text),
    Column("quarantine_reason", Text),
    CheckConstraint("length(trim(mutation_type)) > 0", name="mutation_type_nonempty"),
    CheckConstraint(
        "state IN ('PREPARED', 'COMMITTED', 'QUARANTINED')",
        name="state",
    ),
    CheckConstraint("length(trim(source_reference)) > 0", name="source_reference_nonempty"),
    CheckConstraint("length(trim(staged_reference)) > 0", name="staged_reference_nonempty"),
    CheckConstraint("length(old_sha256) = 64", name="old_sha256_length"),
    CheckConstraint("length(new_sha256) = 64", name="new_sha256_length"),
    CheckConstraint("length(trim(db_mutation_type)) > 0", name="db_mutation_type_nonempty"),
    CheckConstraint("length(trim(db_mutation_id)) > 0", name="db_mutation_id_nonempty"),
    CheckConstraint("length(trim(recovery_strategy)) > 0", name="recovery_strategy_nonempty"),
    CheckConstraint(
        "(state = 'PREPARED' AND committed_at IS NULL AND quarantined_at IS NULL "
        "AND quarantine_reason IS NULL) OR "
        "(state = 'COMMITTED' AND committed_at IS NOT NULL AND quarantined_at IS NULL "
        "AND quarantine_reason IS NULL) OR "
        "(state = 'QUARANTINED' AND committed_at IS NULL AND quarantined_at IS NOT NULL "
        "AND length(trim(quarantine_reason)) > 0)",
        name="state_fields",
    ),
    UniqueConstraint("db_mutation_type", "db_mutation_id"),
)
Index(
    "idx_knowledge_mutation_journal_state",
    knowledge_mutation_journal.c.state,
    knowledge_mutation_journal.c.prepared_at,
    knowledge_mutation_journal.c.id,
)
