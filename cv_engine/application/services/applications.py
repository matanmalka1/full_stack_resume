from __future__ import annotations

import re

from ...domain.models import AuditRecord
from ...util import new_id, normalized_text, sha256_text, utc_now
from ..commands import (
    CreatedJobSnapshot,
    CreateJobSnapshotCommand,
    DuplicateCheckCommand,
    DuplicateCheckResult,
    DuplicateMatch,
    DuplicateMatchReason,
    IngestCommand,
    IngestedApplication,
)
from ..errors import (
    # Re-exported: the API and test suite catch WorkflowError from here, and
    # it is bound to the taxonomy's base class, so every refusal below is caught.
    DuplicateAcknowledgementRequired,
    InfrastructureFailure,
    PreconditionFailed,
    StateConflict,
    UnknownRecord,
)
from ..ports import (
    PreparationRepository,
)
from .base import ServiceBase

JOB_TEXT_MAX_BYTES = 1024 * 1024
SOURCE_URL_MAX_CHARACTERS = 2048
_LABEL_MAX_CHARACTERS = 500
_SOURCE_URL = re.compile(r"https?://[^\s]+\Z", re.IGNORECASE)
_DUPLICATE_WARNING: dict[DuplicateMatchReason, str] = {
    "source_url": "DUPLICATE_SOURCE_URL",
    "normalized_text": "DUPLICATE_NORMALIZED_TEXT",
    "company_title": "DUPLICATE_COMPANY_TITLE",
}
_MATCH_ORDER: tuple[DuplicateMatchReason, ...] = (
    "source_url",
    "normalized_text",
    "company_title",
)


class ApplicationService(ServiceBase[PreparationRepository]):
    """Creating an application and its immutable job snapshot."""

    def duplicate_check(self, command: DuplicateCheckCommand) -> DuplicateCheckResult:
        _validate_intake(command.company, command.target_role, command.job_text, command.source_url)
        normalized_hash = sha256_text(normalized_text(command.job_text))
        company_key = normalized_text(command.company)
        title_key = normalized_text(command.target_role)
        by_application: dict[str, dict] = {}
        for row in self.repo.duplicate_application_inputs():
            matched_on = set()
            if command.source_url is not None and row["source_url"] == command.source_url:
                matched_on.add("source_url")
            if row["normalized_hash"] == normalized_hash:
                matched_on.add("normalized_text")
            if (
                normalized_text(row["company"]) == company_key
                and normalized_text(row["target_role"]) == title_key
            ):
                matched_on.add("company_title")
            if not matched_on:
                continue
            existing = by_application.setdefault(
                row["application_id"],
                {
                    "company": row["company"],
                    "target_role": row["target_role"],
                    "matched_on": set(),
                },
            )
            existing["matched_on"].update(matched_on)
        return DuplicateCheckResult(
            matches=[
                DuplicateMatch(
                    application_id=application_id,
                    company=values["company"],
                    target_role=values["target_role"],
                    matched_on=[
                        reason for reason in _MATCH_ORDER if reason in values["matched_on"]
                    ],
                )
                for application_id, values in by_application.items()
            ]
        )

    def ingest(self, command: IngestCommand) -> IngestedApplication:
        duplicates = self.duplicate_check(
            DuplicateCheckCommand(
                company=command.company,
                target_role=command.target_role,
                job_text=command.job_text,
                source_url=command.source_url,
            )
        )
        if duplicates.matches and not command.acknowledged_duplicates:
            raise DuplicateAcknowledgementRequired(
                "possible duplicate applications require explicit acknowledgement",
                [match.model_dump(mode="json") for match in duplicates.matches],
            )
        try:
            application_id = new_id()
            snapshot_id = new_id()
            payload = self.snapshot_payloads.commit_snapshot(
                application_id,
                snapshot_id,
                command.job_text,
            )
            application_id, snapshot_id = self.repo.create_application(
                company=command.company,
                target_role=command.target_role,
                payload_path=payload.reference,
                source_hash=payload.sha256,
                normalized_hash=sha256_text(normalized_text(command.job_text)),
                source_url=command.source_url,
                application_id=application_id,
                snapshot_id=snapshot_id,
                actor_type=command.actor_type,
                client=command.client,
            )
        except ValueError as exc:
            raise PreconditionFailed(str(exc)) from exc
        except OSError as exc:
            raise InfrastructureFailure(f"could not create application: {exc}") from exc
        return IngestedApplication(
            application_id=application_id,
            job_snapshot_id=snapshot_id,
            warnings=_duplicate_warnings(duplicates.matches),
            duplicate_matches=duplicates.matches,
        )

    def create_job_snapshot(self, command: CreateJobSnapshotCommand) -> CreatedJobSnapshot:
        _validate_job_text(command.job_text)
        _validate_source_url(command.source_url)
        try:
            self.repo.get_application(command.application_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown application: {command.application_id}") from exc
        source_hash = sha256_text(command.job_text)
        if self.repo.snapshot_for_content_hash(command.application_id, source_hash) is not None:
            raise StateConflict("the application already has a snapshot with this exact content")
        snapshot_id = new_id()
        normalized_hash = sha256_text(normalized_text(command.job_text))
        now = utc_now()
        try:
            payload = self.snapshot_payloads.commit_snapshot(
                command.application_id,
                snapshot_id,
                command.job_text,
            )
            with self.repo.unit_of_work() as uow:
                transaction = self.repo.bind(uow)
                created_id = transaction.add_job_snapshot(
                    command.application_id,
                    payload.reference,
                    payload.sha256,
                    normalized_hash,
                    source_url=command.source_url,
                    source_metadata=command.source_metadata,
                    snapshot_id=snapshot_id,
                    captured_at=now,
                )
                transaction.insert_audit(
                    AuditRecord(
                        id=new_id(),
                        application_id=command.application_id,
                        action="create_job_snapshot",
                        entity_type="job_snapshot",
                        entity_id=created_id,
                        actor_type=command.actor_type,
                        client=command.client,
                        occurred_at=now,
                        details={
                            "source_hash": payload.sha256,
                            "normalized_hash": normalized_hash,
                            "source_url": command.source_url,
                        },
                    )
                )
                uow.commit()
        except ValueError as exc:
            raise PreconditionFailed(str(exc)) from exc
        except OSError as exc:
            raise InfrastructureFailure(f"could not create job snapshot: {exc}") from exc
        return CreatedJobSnapshot(
            application_id=command.application_id,
            job_snapshot_id=created_id,
        )


def _duplicate_warnings(matches: list[DuplicateMatch]) -> list[str]:
    matched = {reason for match in matches for reason in match.matched_on}
    return [_DUPLICATE_WARNING[reason] for reason in _MATCH_ORDER if reason in matched]


def _validate_intake(
    company: str,
    target_role: str,
    job_text: str,
    source_url: str | None,
) -> None:
    for label, value in (("company", company), ("target role", target_role)):
        if not value.strip():
            raise PreconditionFailed(f"{label} is required")
        if len(value) > _LABEL_MAX_CHARACTERS:
            raise PreconditionFailed(f"{label} is too long")
        if _has_forbidden_control(value, allow_job_whitespace=False):
            raise PreconditionFailed(f"{label} contains control characters")
    _validate_job_text(job_text)
    _validate_source_url(source_url)


def _validate_job_text(job_text: str) -> None:
    if not job_text.strip():
        raise PreconditionFailed("job text is required")
    if len(job_text.encode("utf-8")) > JOB_TEXT_MAX_BYTES:
        raise PreconditionFailed(f"job text exceeds {JOB_TEXT_MAX_BYTES} bytes")
    if _has_forbidden_control(job_text, allow_job_whitespace=True):
        raise PreconditionFailed("job text contains unsupported control characters")


def _validate_source_url(source_url: str | None) -> None:
    if source_url is None:
        return
    if len(source_url) > SOURCE_URL_MAX_CHARACTERS:
        raise PreconditionFailed(f"source URL exceeds {SOURCE_URL_MAX_CHARACTERS} characters")
    if _has_forbidden_control(source_url, allow_job_whitespace=False):
        raise PreconditionFailed("source URL contains control characters")
    if _SOURCE_URL.fullmatch(source_url) is None:
        raise PreconditionFailed("source URL must be an http or https URL")


def _has_forbidden_control(value: str, *, allow_job_whitespace: bool) -> bool:
    allowed = {"\t", "\n", "\r"} if allow_job_whitespace else set()
    return any(
        (ord(character) < 32 or ord(character) == 127) and character not in allowed
        for character in value
    )
