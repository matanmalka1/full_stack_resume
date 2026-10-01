"""SQLAlchemy Core definitions for the PostgreSQL persistence schema.

Split by domain (prep / tracking / knowledge / shared) as siblings under one
`MetaData`. Re-exported here so importers name one place, matching how
`application/ports/` was already split from a single module.
"""

from __future__ import annotations

from ._metadata import metadata
from .knowledge import fact_events, knowledge_mutation_journal
from .prep import cv_documents, job_analyses, job_snapshots
from .shared import (
    OPERATION_FAILURE_CODES,
    ai_calls,
    app_settings,
    applications,
    audit_records,
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
    "cv_documents",
    "recruitment_events",
    "submissions",
    "ai_calls",
    "audit_records",
    "operations",
    "operation_resource_leases",
    "operation_outputs",
    "app_settings",
    "fact_events",
    "knowledge_mutation_journal",
]
