"""CV-preparation tables: snapshot -> analysis -> the one mutable CV document."""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ._helpers import IsoTimestamp
from ._metadata import metadata

job_snapshots = Table(
    "job_snapshots",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("application_id", UUID(as_uuid=False), ForeignKey("applications.id"), nullable=False),
    Column("version_number", Integer, nullable=False),
    Column("payload_path", Text, nullable=False),
    Column("source_hash", Text, nullable=False),
    Column("normalized_hash", Text, nullable=False),
    Column("source_url", Text),
    Column("captured_at", IsoTimestamp(), nullable=False),
    Column("source_metadata_json", JSONB, nullable=False),
    CheckConstraint("version_number > 0", name="version_number_positive"),
    UniqueConstraint("application_id", "version_number"),
    UniqueConstraint("application_id", "source_hash"),
    UniqueConstraint("application_id", "id"),
)

job_analyses = Table(
    "job_analyses",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("application_id", UUID(as_uuid=False), ForeignKey("applications.id"), nullable=False),
    Column("job_snapshot_id", UUID(as_uuid=False), nullable=False),
    Column("version_number", Integer, nullable=False),
    Column("structured_json", JSONB, nullable=False),
    Column("provider", Text, nullable=False),
    Column("model", Text, nullable=False),
    Column("created_at", IsoTimestamp(), nullable=False),
    CheckConstraint("version_number > 0", name="version_number_positive"),
    UniqueConstraint("application_id", "version_number"),
    UniqueConstraint("application_id", "id"),
    ForeignKeyConstraint(
        ("application_id", "job_snapshot_id"),
        ("job_snapshots.application_id", "job_snapshots.id"),
    ),
)


# The one mutable CV document per Application (state-and-use-cases.md §3). Only the
# three basis stamps are stored; the basis itself is computed on read, so a stamp that
# no longer equals it is outdated without any write.
cv_documents = Table(
    "cv_documents",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column(
        "application_id",
        UUID(as_uuid=False),
        ForeignKey("applications.id"),
        nullable=False,
        unique=True,
    ),
    Column("analysis_id", UUID(as_uuid=False), nullable=False),
    Column("selection", JSONB, nullable=False),
    Column("content", JSONB(none_as_null=True)),
    Column("profile_version", Text, nullable=False),
    Column("selection_policy_version", Text, nullable=False),
    Column("document_hash", Text, nullable=False),
    Column("content_report", JSONB(none_as_null=True)),
    Column("checked_basis", Text),
    Column("passed", Boolean),
    Column("approved_basis", Text),
    Column("approved_at", IsoTimestamp()),
    Column("rendered_basis", Text),
    Column("html_path", Text, unique=True),
    Column("pdf_path", Text, unique=True),
    Column("last_render_error", JSONB(none_as_null=True)),
    Column("created_at", IsoTimestamp(), nullable=False),
    Column("updated_at", IsoTimestamp(), nullable=False),
    CheckConstraint("length(document_hash) = 64", name="document_hash_length"),
    CheckConstraint(
        "(checked_basis IS NULL OR length(checked_basis) = 64) "
        "AND (approved_basis IS NULL OR length(approved_basis) = 64) "
        "AND (rendered_basis IS NULL OR length(rendered_basis) = 64)",
        name="basis_length",
    ),
    CheckConstraint(
        "(content_report IS NULL) = (checked_basis IS NULL) "
        "AND (checked_basis IS NULL) = (passed IS NULL)",
        name="check_stamp",
    ),
    CheckConstraint("(approved_basis IS NULL) = (approved_at IS NULL)", name="approval_stamp"),
    CheckConstraint(
        "(rendered_basis IS NULL) = (html_path IS NULL) "
        "AND (html_path IS NULL) = (pdf_path IS NULL)",
        name="render_stamp",
    ),
    CheckConstraint(
        "content IS NOT NULL OR (checked_basis IS NULL AND approved_basis IS NULL "
        "AND rendered_basis IS NULL AND last_render_error IS NULL)",
        name="empty_document_unstamped",
    ),
    CheckConstraint(
        "last_render_error IS NULL OR "
        "(jsonb_typeof(last_render_error) = 'object' AND last_render_error ? 'code')",
        name="last_render_error_shape",
    ),
    ForeignKeyConstraint(
        ("application_id", "analysis_id"),
        ("job_analyses.application_id", "job_analyses.id"),
    ),
)
