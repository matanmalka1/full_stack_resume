"""Revision-model tables dropped by migration 0002. Temporary: removed in Wave 3.

The single-document rewrite (docs/backlog/single-document-rewrite.md) drops these
tables in Wave 1, while the services that still name them are rewritten by the Wave 2
lanes. These column-only shapes keep those modules importable in the meantime. They
live on their own `MetaData`, so they are never created, never compared against the
schema, and never counted as product tables; any statement built from them fails at
execution because the table no longer exists.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Column, Integer, MetaData, Table, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ._helpers import IsoTimestamp

legacy_metadata = MetaData()

selection_plans = Table(
    "selection_plans",
    legacy_metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("application_id", UUID(as_uuid=False)),
    Column("job_analysis_id", UUID(as_uuid=False)),
    Column("version_number", Integer),
    Column("plan_json", JSONB),
    Column("candidate_context_version", Text),
    Column("candidate_context_hash", Text),
    Column("profile_version", Text),
    Column("selection_policy_version", Text),
    Column("track_emphasis_dependencies_json", JSONB),
    Column("created_at", IsoTimestamp()),
)

working_drafts = Table(
    "working_drafts",
    legacy_metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("application_id", UUID(as_uuid=False)),
    Column("job_analysis_id", UUID(as_uuid=False)),
    Column("selection_plan_id", UUID(as_uuid=False)),
    Column("parent_revision_id", UUID(as_uuid=False)),
    Column("source_json", JSONB),
    Column("edit_version", Integer),
    Column("content_hash", Text),
    Column("active", Boolean),
    Column("created_at", IsoTimestamp()),
    Column("updated_at", IsoTimestamp()),
)

approved_revisions = Table(
    "approved_revisions",
    legacy_metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("application_id", UUID(as_uuid=False)),
    Column("version_number", Integer),
    Column("job_snapshot_id", UUID(as_uuid=False)),
    Column("job_analysis_id", UUID(as_uuid=False)),
    Column("selection_plan_id", UUID(as_uuid=False)),
    Column("working_draft_id", UUID(as_uuid=False)),
    Column("draft_edit_version", Integer),
    Column("draft_content_hash", Text),
    Column("resume_json_path", Text),
    Column("resume_json_hash", Text),
    Column("resume_markdown_path", Text),
    Column("resume_markdown_hash", Text),
    Column("candidate_context_version", Text),
    Column("candidate_context_hash", Text),
    Column("facts_version", Text),
    Column("knowledge_context_hash", Text),
    Column("profile_version", Text),
    Column("selection_policy_version", Text),
    Column("track_emphasis_dependencies_json", JSONB),
    Column("validation_run_id", UUID(as_uuid=False)),
    Column("validator_versions_json", JSONB),
    Column("decision_provenance_json", JSONB),
    Column("approved_at", IsoTimestamp()),
)

decision_records = Table(
    "decision_records",
    legacy_metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("approved_revision_id", UUID(as_uuid=False)),
    Column("structured_json", JSONB),
    Column("summary", Text),
    Column("created_at", IsoTimestamp()),
)

validation_runs = Table(
    "validation_runs",
    legacy_metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("seq", BigInteger),
    Column("application_id", UUID(as_uuid=False)),
    Column("artifact_version_id", UUID(as_uuid=False)),
    Column("phase", Text),
    Column("report_json", JSONB),
    Column("created_at", IsoTimestamp()),
    Column("working_draft_id", UUID(as_uuid=False)),
    Column("edit_version", Integer),
    Column("content_hash", Text),
    Column("job_snapshot_id", UUID(as_uuid=False)),
    Column("job_analysis_id", UUID(as_uuid=False)),
    Column("selection_plan_id", UUID(as_uuid=False)),
    Column("knowledge_context_hash", Text),
    Column("validator_versions_json", JSONB),
)
