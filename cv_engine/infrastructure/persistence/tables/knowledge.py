"""Knowledge/facts tables: fact lifecycle audit, the mutation journal, and per-user Knowledge.

`facts`, `candidate_contexts` and `profile_bindings` are the per-user Knowledge of
architecture §18.2. They are seeded by `import-knowledge` and are the live Knowledge
read and written by the application.
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ....domain.knowledge_import import FACT_SOURCES
from ._helpers import IsoTimestamp, sequence_column, sql_values
from ._metadata import metadata

fact_events = Table(
    "fact_events",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    sequence_column("fact_events"),
    Column("fact_id", String, nullable=False),
    Column("source_file", Text, nullable=False),
    Column("event_type", Text, nullable=False),
    Column("from_status", Text),
    Column("to_status", Text, nullable=False),
    Column("application_id", UUID(as_uuid=False), ForeignKey("applications.id")),
    Column("claim_id", String),
    Column("reason", Text, nullable=False, server_default=text("''")),
    Column("fact_json", JSONB, nullable=False),
    Column("fact_hash", Text, nullable=False),
    Column("facts_version", Text, nullable=False),
    Column("lifecycle_version", Text, nullable=False),
    Column("created_at", IsoTimestamp(), nullable=False),
    Column("user_id", UUID(as_uuid=False), ForeignKey("users.id"), nullable=False),
)
Index(
    "idx_fact_events_fact",
    fact_events.c.fact_id,
    fact_events.c.created_at,
    fact_events.c.seq,
)

knowledge_mutation_journal = Table(
    "knowledge_mutation_journal",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
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
    Column("prepared_at", IsoTimestamp(), nullable=False),
    Column("committed_at", IsoTimestamp()),
    Column("quarantined_at", IsoTimestamp()),
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


FACT_STATUSES = ("pending", "canonical", "deleted")
RESUME_STYLES = ("paragraph", "heading", "date", "bullet", "item", "contact")

#: One row per fact of a user, at its current status and content. A fact is edited in
#: place (docs/decisions/editable-facts.md), so a trigger guards only its identity - `id`,
#: `user_id`, `fact_id`, `source`, `ordinal`, `created_at` - and refuses every delete:
#: deletion is a status.
facts = Table(
    "facts",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("user_id", UUID(as_uuid=False), ForeignKey("users.id"), nullable=False),
    Column("fact_id", String, nullable=False),
    Column("status", Text, nullable=False),
    Column("source", Text, nullable=False),
    Column("ordinal", Integer, nullable=False),
    Column("meaning", Text, nullable=False),
    Column("renderings", JSONB, nullable=False),
    Column("tags", JSONB, nullable=False),
    Column("provenance", Text, nullable=False),
    Column("effective_dates", Text),
    Column("resume_style", Text, nullable=False),
    Column("link_target", Text),
    # History only: the fact this one was recorded as correcting, as imported. No foreign
    # key: imported facts may name v1 ids that exist in no fact source.
    Column("replaces", String),
    # As the fact carried it (a date string, or none): never re-derived.
    Column("confirmed_at", Text),
    Column("created_at", IsoTimestamp(), nullable=False),
    Column("updated_at", IsoTimestamp(), nullable=False),
    UniqueConstraint("user_id", "fact_id"),
    UniqueConstraint("user_id", "source", "ordinal"),
    CheckConstraint(f"status IN ({sql_values(FACT_STATUSES)})", name="status"),
    CheckConstraint(f"source IN ({sql_values(FACT_SOURCES)})", name="source"),
    CheckConstraint(f"resume_style IN ({sql_values(RESUME_STYLES)})", name="resume_style"),
    CheckConstraint("ordinal > 0", name="ordinal_positive"),
)

#: The declared candidate context, one per user; what is resolved from facts is not stored.
candidate_contexts = Table(
    "candidate_contexts",
    metadata,
    Column("user_id", UUID(as_uuid=False), ForeignKey("users.id"), primary_key=True),
    Column("context_version", Text, nullable=False),
    Column("name_fact_id", String, nullable=False),
    Column("filename_name", Text),
    Column("filename_language", Text, nullable=False),
    Column("locale", Text, nullable=False),
    Column("timezone", Text, nullable=False),
    Column("contact_fact_ids", JSONB, nullable=False),
    Column("track_contact_fact_ids", JSONB, nullable=False),
    Column("link_schemes", JSONB, nullable=False),
    # Advanced by every fact mutation once Knowledge lives here (architecture §18.2).
    Column("fact_store_version", Integer, nullable=False),
    Column("updated_at", IsoTimestamp(), nullable=False),
    CheckConstraint("filename_language IN ('en', 'he')", name="filename_language"),
    CheckConstraint("fact_store_version >= 0", name="fact_store_version"),
)

#: A user's part of one Profile template: section pools and pins, safe headlines, and
#: omitted roles (`domain.knowledge_import.split_profile`).
profile_bindings = Table(
    "profile_bindings",
    metadata,
    Column("user_id", UUID(as_uuid=False), ForeignKey("users.id"), primary_key=True),
    Column("profile_id", Text, primary_key=True),
    Column("binding", JSONB, nullable=False),
    Column("binding_version", Integer, nullable=False),
    Column("updated_at", IsoTimestamp(), nullable=False),
    CheckConstraint("binding_version > 0", name="binding_version"),
)
