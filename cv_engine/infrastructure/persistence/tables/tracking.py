"""Recruitment-pipeline tables: status history, next action, submissions."""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Table,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ._helpers import IsoTimestamp, sequence_column, sql_values
from ._metadata import metadata
from .shared import RECRUITMENT_STATUSES

recruitment_events = Table(
    "recruitment_events",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    sequence_column("recruitment_events"),
    Column("application_id", UUID(as_uuid=False), ForeignKey("applications.id"), nullable=False),
    Column("event_type", Text, nullable=False),
    Column("from_status", Text),
    Column("to_status", Text),
    Column("corrects_event_id", UUID(as_uuid=False), ForeignKey("recruitment_events.id")),
    Column("reason", Text, nullable=False, server_default=text("''")),
    Column("actor_type", Text, nullable=False),
    Column("client", Text, nullable=False),
    Column("occurred_at", IsoTimestamp(), nullable=False),
    Column("payload_json", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", IsoTimestamp(), nullable=False),
    CheckConstraint(
        "event_type IN ('status_transition', 'status_correction', 'next_action')",
        name="event_type",
    ),
    CheckConstraint(
        f"from_status IS NULL OR from_status IN ({sql_values(RECRUITMENT_STATUSES)})",
        name="from_status",
    ),
    CheckConstraint(
        f"to_status IS NULL OR to_status IN ({sql_values(RECRUITMENT_STATUSES)})",
        name="to_status",
    ),
    CheckConstraint("actor_type IN ('user', 'system')", name="actor_type"),
    CheckConstraint("client IN ('web', 'worker')", name="client"),
    CheckConstraint(
        "event_type != 'status_correction' OR "
        "(corrects_event_id IS NOT NULL AND length(trim(reason)) > 0)",
        name="correction_reason",
    ),
    CheckConstraint(
        "event_type = 'status_correction' OR corrects_event_id IS NULL",
        name="correction_reference",
    ),
)
Index(
    "idx_recruitment_events_application",
    recruitment_events.c.application_id,
    recruitment_events.c.occurred_at,
    recruitment_events.c.seq,
)

# A Submission records a send that already happened (state-and-use-cases.md §18). An
# internal one copies the document content and rendered files it sent, each file with
# its own SHA-256; an external one carries none of them.
_INTERNAL_REFERENCES = (
    "job_text_hash",
    "document_hash",
    "content",
    "html_path",
    "html_sha256",
    "pdf_path",
    "pdf_sha256",
)

submissions = Table(
    "submissions",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    sequence_column("submissions"),
    Column("application_id", UUID(as_uuid=False), ForeignKey("applications.id"), nullable=False),
    Column("submission_type", Text, nullable=False),
    # The Application's job text when this was sent; the text locks from here on.
    Column("job_text_hash", Text),
    Column("document_hash", Text),
    Column("content", JSONB(none_as_null=True)),
    Column("html_path", Text, unique=True),
    Column("html_sha256", Text),
    Column("pdf_path", Text, unique=True),
    Column("pdf_sha256", Text),
    Column("submitted_at", IsoTimestamp(), nullable=False),
    Column("metadata_json", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    CheckConstraint("submission_type IN ('internal', 'external')", name="submission_type"),
    CheckConstraint(
        "(submission_type = 'internal' AND "
        + " AND ".join(f"{name} IS NOT NULL" for name in _INTERNAL_REFERENCES)
        + ") OR (submission_type = 'external' AND "
        + " AND ".join(f"{name} IS NULL" for name in _INTERNAL_REFERENCES)
        + ")",
        name="references",
    ),
    CheckConstraint(
        "(job_text_hash IS NULL OR length(job_text_hash) = 64) "
        "AND (document_hash IS NULL OR length(document_hash) = 64) "
        "AND (html_sha256 IS NULL OR length(html_sha256) = 64) "
        "AND (pdf_sha256 IS NULL OR length(pdf_sha256) = 64)",
        name="hash_length",
    ),
)
Index(
    "idx_submissions_application",
    submissions.c.application_id,
    submissions.c.submitted_at,
    submissions.c.seq,
)
