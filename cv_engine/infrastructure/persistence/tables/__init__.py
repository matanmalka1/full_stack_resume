"""SQLAlchemy Core definitions for the PostgreSQL persistence schema.

Split by domain (prep / tracking / knowledge / shared) as siblings under one
`MetaData`. Re-exported here so importers name one place, matching how
`application/ports/` was already split from a single module.
"""

from __future__ import annotations

from ._metadata import metadata
from .knowledge import fact_events, knowledge_mutation_journal
from .legacy import (  # temporary re-export: removed in Wave 3
    approved_revisions,
    decision_records,
    selection_plans,
    validation_runs,
    working_drafts,
)
from .prep import cv_documents, job_analyses, job_snapshots
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
    payload_write_leases,
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
    "cv_documents",
    "selection_plans",
    "working_drafts",
    "approved_revisions",
    "decision_records",
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
    "payload_write_leases",
    "app_settings",
    "fact_events",
    "knowledge_mutation_journal",
]
