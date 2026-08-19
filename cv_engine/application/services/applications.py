from __future__ import annotations

from ...util import new_id, normalized_text, sha256_text
from ..commands import (
    IngestCommand,
    IngestedApplication,
)
from ..errors import (
    # Re-exported: the v1 CLI and test suite catch WorkflowError from here, and
    # it is bound to the taxonomy's base class, so every refusal below is caught.
    InfrastructureFailure,
    PreconditionFailed,
)
from ..ports import (
    ApplicationStore,
)
from .base import ServiceBase


class ApplicationService(ServiceBase[ApplicationStore]):
    """Creating an application and its immutable job snapshot."""

    def ingest(self, command: IngestCommand) -> IngestedApplication:
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
            )
        except ValueError as exc:
            raise PreconditionFailed(str(exc)) from exc
        except OSError as exc:
            raise InfrastructureFailure(f"could not create application: {exc}") from exc
        return IngestedApplication(
            application_id=application_id,
            job_snapshot_id=snapshot_id,
        )
