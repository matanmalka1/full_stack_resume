"""Read-side helpers over the provider-response artifact catalog.

Rendered and approved outputs live on the CV document and on Submissions
(docs/decisions/single-document-model.md §4); the only artifact family left is AI
provenance, which `provider_evidence` registers together with its Operation output.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Connection

from ...application.errors import UnknownRecord
from .base import json_text_record
from .tables import artifact_versions, artifacts


def _artifact_version(connection: Connection, artifact_version_id: str) -> dict[str, Any]:
    row = (
        connection.execute(
            select(
                *artifact_versions.c,
                artifacts.c.application_id,
                artifacts.c.artifact_type,
                artifacts.c.logical_name,
            )
            .select_from(artifact_versions.join(artifacts))
            .where(artifact_versions.c.id == artifact_version_id)
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise UnknownRecord(f"no artifact version {artifact_version_id}")
    return json_text_record(row, "metadata_json")


def _artifact_versions(connection: Connection, application_id: str) -> list[dict[str, Any]]:
    rows = (
        connection.execute(
            select(*artifact_versions.c, artifacts.c.artifact_type, artifacts.c.logical_name)
            .select_from(artifact_versions.join(artifacts))
            .where(artifacts.c.application_id == application_id)
            .order_by(artifact_versions.c.created_at, artifact_versions.c.version_number)
        )
        .mappings()
        .all()
    )
    return [json_text_record(row, "metadata_json") for row in rows]


def _latest_artifact_version(
    connection: Connection,
    application_id: str,
    artifact_type: str,
    lifecycle_status: str | None = None,
) -> dict[str, Any]:
    statement = (
        select(*artifact_versions.c, artifacts.c.artifact_type, artifacts.c.logical_name)
        .select_from(artifact_versions.join(artifacts))
        .where(
            artifacts.c.application_id == application_id, artifacts.c.artifact_type == artifact_type
        )
    )
    if lifecycle_status:
        statement = statement.where(artifact_versions.c.lifecycle_status == lifecycle_status)
    statement = statement.order_by(
        artifact_versions.c.created_at.desc(), artifact_versions.c.version_number.desc()
    ).limit(1)
    row = connection.execute(statement).mappings().one_or_none()
    if row is None:
        raise UnknownRecord(f"no {artifact_type} artifact for application {application_id}")
    return json_text_record(row, "metadata_json")
