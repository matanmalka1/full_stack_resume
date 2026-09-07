"""SQLAlchemy Core definitions for the PostgreSQL persistence schema.

Split by domain (prep / tracking / knowledge / shared) as siblings under one
`MetaData`. Re-exported here so importers name one place, matching how
`application/ports/` was already split from a single module.
"""

from __future__ import annotations

from ._metadata import metadata
from .knowledge import fact_events, knowledge_mutation_journal
from .prep import (
    approved_revisions,
    decision_records,
    draft_lifecycle_events,
    generation_runs,
    job_analyses,
    job_snapshots,
    selection_plans,
    validation_runs,
    working_drafts,
)
from .shared import (
    OPERATION_FAILURE_CODES,
    app_settings,
    applications,
    artifact_versions,
    artifacts,
    audit_records,
    idempotency_receipts,
    operation_outputs,
    operation_resource_leases,
    operations,
)
from .tracking import recruitment_events, submissions

TABLES = tuple(metadata.tables.values())

__all__ = [
    "metadata",
    "TABLES",
    "OPERATION_FAILURE_CODES",
    "applications",
    "job_snapshots",
    "job_analyses",
    "selection_plans",
    "working_drafts",
    "draft_lifecycle_events",
    "approved_revisions",
    "decision_records",
    "generation_runs",
    "validation_runs",
    "recruitment_events",
    "submissions",
    "artifacts",
    "artifact_versions",
    "audit_records",
    "operations",
    "operation_resource_leases",
    "operation_outputs",
    "idempotency_receipts",
    "app_settings",
    "fact_events",
    "knowledge_mutation_journal",
]
