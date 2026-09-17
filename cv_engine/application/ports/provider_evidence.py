"""Durable inactive provider evidence, before any result can be activated."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ...domain.contracts.providers import ProviderTaskResult
from .transactions import ReadTransaction, WriteTransaction
from .values import SnapshotPayload


@dataclass(frozen=True)
class StoredProviderResponse:
    artifact_version_id: str
    payload: SnapshotPayload


class ProviderEvidenceStore(Protocol):
    def find_response(
        self,
        tx: ReadTransaction,
        application_id: str,
        operation_id: str,
        task: str,
        provenance: ProviderTaskResult,
    ) -> StoredProviderResponse | None: ...

    def register_inactive(
        self,
        tx: WriteTransaction,
        application_id: str,
        operation_id: str,
        task: str,
        provenance: ProviderTaskResult,
        response: StoredProviderResponse,
    ) -> StoredProviderResponse: ...
