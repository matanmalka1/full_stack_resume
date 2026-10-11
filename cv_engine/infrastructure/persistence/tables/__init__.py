"""SQLAlchemy Core definitions for the PostgreSQL persistence schema.

Split by domain (prep / tracking / knowledge / shared) as siblings under one
`MetaData`. Re-exported here so importers name one place, matching how
`application/ports/` was already split from a single module.
"""

from __future__ import annotations

from ._metadata import metadata
from .accounts import user_sessions, users
from .knowledge import (
    candidate_contexts,
    fact_events,
    facts,
    knowledge_mutation_journal,
    profile_bindings,
)
from .prep import cv_documents, job_analyses
from .shared import (
    OPERATION_FAILURE_CODES,
    ai_calls,
    app_settings,
    applications,
    audit_records,
    operation_outputs,
    operations,
)
from .tracking import recruitment_events, submissions

TABLES = tuple(metadata.tables.values())

__all__ = [
    "metadata",
    "TABLES",
    "OPERATION_FAILURE_CODES",
    "applications",
    "job_analyses",
    "cv_documents",
    "recruitment_events",
    "submissions",
    "ai_calls",
    "audit_records",
    "operations",
    "operation_outputs",
    "app_settings",
    "fact_events",
    "knowledge_mutation_journal",
    "users",
    "user_sessions",
    "facts",
    "candidate_contexts",
    "profile_bindings",
]
