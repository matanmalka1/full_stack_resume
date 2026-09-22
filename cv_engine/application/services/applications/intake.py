from __future__ import annotations

import re
from typing import Literal

from ....domain.contracts.records import AuditRecord
from ....util import new_id, normalized_text, sha256_text, utc_now
from ...commands import (
    CreatedJobSnapshot,
    CreateJobSnapshotCommand,
    DuplicateCheckCommand,
    DuplicateCheckResult,
    DuplicateMatch,
    DuplicateMatchReason,
    IngestCommand,
    IngestedApplication,
    UpdateApplicationNotesCommand,
    UpdatedApplicationNotes,
)
from ...commands.prep import SOURCE_URL_MAX_CHARACTERS
from ...errors import (
    # Re-exported: the API and test suite catch WorkflowError from here, and
    # it is bound to the taxonomy's base class, so every refusal below is caught.
    ApplicationIntakeInvalid,
    DuplicateAcknowledgementRequired,
    InfrastructureFailure,
    PreconditionFailed,
    StateConflict,
    UnknownRecord,
)
from ...ports import SnapshotPayload, SnapshotPayloadStore
from ...ports.application_intake import (
    AuditLogWriter,
    InitialRecruitmentEventWriter,
    IntakeApplicationStore,
    JobSnapshotStore,
)
from ...ports.payload_leases import DEFAULT_LEASE_TTL_SECONDS, PayloadWriteLeaseStore
from ...ports.transactions import TransactionManager, WriteTransaction

JOB_TEXT_MAX_BYTES = 1024 * 1024
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


class ApplicationService:
    """Creating an application and its immutable job snapshot."""

    def __init__(
        self,
        *,
        transactions: TransactionManager,
        applications: IntakeApplicationStore,
        snapshots: JobSnapshotStore,
        recruitment: InitialRecruitmentEventWriter,
        audit: AuditLogWriter,
        payloads: SnapshotPayloadStore,
        leases: PayloadWriteLeaseStore,
    ):
        self._transactions = transactions
        self._applications = applications
        self._snapshots = snapshots
        self._recruitment = recruitment
        self._audit = audit
        self._payloads = payloads
        self._leases = leases

    def _write_snapshot_payload(
        self, application_id: str, snapshot_id: str, job_text: str
    ) -> SnapshotPayload:
        """Write one JobSnapshot payload under its own write lease (architecture.md §7.1).

        The reference is single-file and already unique per call - `snapshot_id`
        is freshly minted by every caller - so it serves as its own group key
        and attempt_id; there is no separate attempt identity to track.
        """
        reference = self._payloads.reference_for(
            self._payloads.snapshot_path(application_id, snapshot_id)
        )
        with self._transactions.write() as tx:
            self._leases.acquire(
                tx, reference, reference, keys=[reference], ttl_seconds=DEFAULT_LEASE_TTL_SECONDS
            )
        try:
            return self._payloads.commit_snapshot(application_id, snapshot_id, job_text)
        except Exception:
            with self._transactions.write() as tx:
                self._leases.release(tx, reference, reference)
            raise

    def _mark_snapshot_committed(self, tx: WriteTransaction, payload: SnapshotPayload) -> None:
        self._leases.mark_committed(
            tx, payload.reference, payload.reference, keys=[payload.reference]
        )

    def duplicate_check(self, command: DuplicateCheckCommand) -> DuplicateCheckResult:
        _validate_intake(command.company, command.target_role, command.job_text, command.source_url)
        normalized_hash = sha256_text(normalized_text(command.job_text))
        company_key = normalized_text(command.company)
        title_key = normalized_text(command.target_role)
        by_application: dict[str, dict] = {}
        with self._transactions.read() as tx:
            stored_inputs = self._snapshots.duplicate_application_inputs(tx)
        for row in stored_inputs:
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
            payload = self._write_snapshot_payload(application_id, snapshot_id, command.job_text)
            now = utc_now()
            with self._transactions.write() as tx:
                self._mark_snapshot_committed(tx, payload)
                self._applications.insert_application(
                    tx,
                    application_id=application_id,
                    company=command.company,
                    target_role=command.target_role,
                    source_url=command.source_url,
                    notes="",
                    source="manual",
                    created_at=now,
                )
                self._snapshots.insert_initial_snapshot(
                    tx,
                    snapshot_id=snapshot_id,
                    application_id=application_id,
                    payload_path=payload.reference,
                    source_hash=payload.sha256,
                    normalized_hash=sha256_text(normalized_text(command.job_text)),
                    source_url=command.source_url,
                    source_metadata={},
                    captured_at=now,
                )
                self._recruitment.insert_initial_saved_event(
                    tx,
                    application_id=application_id,
                    actor_type=command.actor_type,
                    client=command.client,
                    occurred_at=now,
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
        source_hash = sha256_text(command.job_text)
        snapshot_id = new_id()
        normalized_hash = sha256_text(normalized_text(command.job_text))
        now = utc_now()
        try:
            with self._transactions.read() as tx:
                try:
                    self._applications.get_application(tx, command.application_id)
                except UnknownRecord as exc:
                    raise UnknownRecord(f"unknown application: {command.application_id}") from exc
                duplicate = self._snapshots.snapshot_for_content_hash(
                    tx, command.application_id, source_hash
                )
            if duplicate is not None:
                raise StateConflict(
                    "the application already has a snapshot with this exact content"
                )
            payload = self._write_snapshot_payload(
                command.application_id, snapshot_id, command.job_text
            )
            with self._transactions.write() as tx:
                self._applications.get_application(tx, command.application_id)
                if (
                    self._snapshots.snapshot_for_content_hash(
                        tx, command.application_id, source_hash
                    )
                    is not None
                ):
                    raise StateConflict(
                        "the application already has a snapshot with this exact content"
                    )
                self._mark_snapshot_committed(tx, payload)
                self._snapshots.insert_next_snapshot(
                    tx,
                    snapshot_id=snapshot_id,
                    application_id=command.application_id,
                    payload_path=payload.reference,
                    source_hash=payload.sha256,
                    normalized_hash=normalized_hash,
                    source_url=command.source_url,
                    source_metadata=command.source_metadata,
                    captured_at=now,
                )
                self._audit.insert_audit(
                    tx,
                    AuditRecord(
                        id=new_id(),
                        application_id=command.application_id,
                        action="create_job_snapshot",
                        entity_type="job_snapshot",
                        entity_id=snapshot_id,
                        actor_type=command.actor_type,
                        client=command.client,
                        occurred_at=now,
                        details={
                            "source_hash": payload.sha256,
                            "normalized_hash": normalized_hash,
                            "source_url": command.source_url,
                        },
                    ),
                )
        except ValueError as exc:
            raise PreconditionFailed(str(exc)) from exc
        except OSError as exc:
            raise InfrastructureFailure(f"could not create job snapshot: {exc}") from exc
        return CreatedJobSnapshot(
            application_id=command.application_id,
            job_snapshot_id=snapshot_id,
        )

    def update_notes(self, command: UpdateApplicationNotesCommand) -> UpdatedApplicationNotes:
        now = utc_now()
        with self._transactions.write() as tx:
            updated = self._applications.update_application_notes(
                tx,
                command.application_id,
                command.notes,
                command.expected_notes,
                updated_at=now,
            )
            self._audit.insert_audit(
                tx,
                AuditRecord(
                    id=new_id(),
                    application_id=command.application_id,
                    action="update_application_notes",
                    entity_type="application",
                    entity_id=command.application_id,
                    actor_type=command.actor_type,
                    client=command.client,
                    occurred_at=now,
                    details={"field": "notes"},
                ),
            )
        return UpdatedApplicationNotes(
            application_id=command.application_id,
            notes=updated["notes"],
            updated_at=updated["updated_at"],
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
    labels: tuple[tuple[Literal["company", "target_role"], str, str], ...] = (
        ("company", "company", company),
        ("target_role", "target role", target_role),
    )
    for field, label, value in labels:
        if not value.strip():
            raise ApplicationIntakeInvalid(field, f"{label} is required")
        if len(value) > _LABEL_MAX_CHARACTERS:
            raise ApplicationIntakeInvalid(field, f"{label} is too long")
        if _has_forbidden_control(value, allow_job_whitespace=False):
            raise ApplicationIntakeInvalid(field, f"{label} contains control characters")
    _validate_job_text(job_text)
    _validate_source_url(source_url)


def _validate_job_text(job_text: str) -> None:
    if not job_text.strip():
        raise ApplicationIntakeInvalid("job_text", "job text is required")
    if len(job_text.encode("utf-8")) > JOB_TEXT_MAX_BYTES:
        raise ApplicationIntakeInvalid("job_text", f"job text exceeds {JOB_TEXT_MAX_BYTES} bytes")
    if _has_forbidden_control(job_text, allow_job_whitespace=True):
        raise ApplicationIntakeInvalid(
            "job_text", "job text contains unsupported control characters"
        )


def _validate_source_url(source_url: str | None) -> None:
    if source_url is None:
        return
    if len(source_url) > SOURCE_URL_MAX_CHARACTERS:
        raise ApplicationIntakeInvalid(
            "source_url", f"source URL exceeds {SOURCE_URL_MAX_CHARACTERS} characters"
        )
    if _has_forbidden_control(source_url, allow_job_whitespace=False):
        raise ApplicationIntakeInvalid("source_url", "source URL contains control characters")
    if _SOURCE_URL.fullmatch(source_url) is None:
        raise ApplicationIntakeInvalid("source_url", "source URL must be an http or https URL")


def _has_forbidden_control(value: str, *, allow_job_whitespace: bool) -> bool:
    allowed = {"\t", "\n", "\r"} if allow_job_whitespace else set()
    return any(
        (ord(character) < 32 or ord(character) == 127) and character not in allowed
        for character in value
    )
