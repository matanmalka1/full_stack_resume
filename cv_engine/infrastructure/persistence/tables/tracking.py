"""Recruitment-pipeline tables: status history, next action, submissions."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, String, Table, Text, text
from sqlalchemy.dialects.postgresql import JSONB

from ._helpers import sequence_column, sql_values
from ._metadata import metadata
from .shared import RECRUITMENT_STATUSES

recruitment_events = Table(
    "recruitment_events",
    metadata,
    Column("id", String, primary_key=True),
    sequence_column("recruitment_events"),
    Column("application_id", String, ForeignKey("applications.id"), nullable=False),
    Column("event_type", Text, nullable=False),
    Column("from_status", Text),
    Column("to_status", Text),
    Column("corrects_event_id", String, ForeignKey("recruitment_events.id")),
    Column("reason", Text, nullable=False, server_default=text("''")),
    Column("actor_type", Text, nullable=False),
    Column("client", Text, nullable=False),
    Column("occurred_at", Text, nullable=False),
    Column("payload_json", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", Text, nullable=False),
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

submissions = Table(
    "submissions",
    metadata,
    Column("id", String, primary_key=True),
    sequence_column("submissions"),
    Column("application_id", String, ForeignKey("applications.id"), nullable=False),
    Column("submission_type", Text, nullable=False),
    Column("approved_revision_id", String, ForeignKey("approved_revisions.id")),
    Column("artifact_version_id", String, ForeignKey("artifact_versions.id"), unique=True),
    Column("submitted_at", Text, nullable=False),
    Column("metadata_json", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    CheckConstraint("submission_type IN ('internal', 'external')", name="submission_type"),
    CheckConstraint(
        "(submission_type = 'internal' AND approved_revision_id IS NOT NULL "
        "AND artifact_version_id IS NOT NULL) OR "
        "(submission_type = 'external' AND approved_revision_id IS NULL)",
        name="references",
    ),
)
Index(
    "idx_submissions_application",
    submissions.c.application_id,
    submissions.c.submitted_at,
    submissions.c.seq,
)
