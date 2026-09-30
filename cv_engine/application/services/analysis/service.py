from __future__ import annotations

from ....domain.contracts.document import CVDocument
from ....domain.contracts.providers import ProviderTaskResult
from ....domain.knowledge import Knowledge
from ....util import new_id
from ...commands import (
    AnalysisDecisionsResult,
    AnalysisResult,
    AnalyzeCommand,
    ApplyAnalysisDecisionsCommand,
)
from ...errors import InfrastructureFailure, LineageBroken, ProviderNotConfigured, StateConflict
from ...ports import AIProvider, TransactionManager
from ...ports.analysis_plans import (
    AnalysisContextSource,
    AnalysisContextSourceReader,
    AnalysisKnowledgeSource,
    AnalysisPayloadStore,
    AnalysisSnapshotSource,
    AnalysisStore,
)
from ...ports.documents import DocumentStore
from ...ports.provider_evidence import ProviderEvidenceStore, StoredProviderResponse
from ...transactions import assert_external_io_allowed
from ..documents import DocumentSource, load_knowledge, read_document_source
from ..proposals import ProviderEvidence
from .activation import AnalysisActivation
from .correction import AnalysisCorrection
from .preparation import AnalysisPreparation, PreparedAnalysis


class AnalysisService:
    """Own preparation scopes and synchronous analysis transaction boundaries."""

    def __init__(
        self,
        *,
        transactions: TransactionManager,
        analyses: AnalysisStore,
        sources: AnalysisContextSourceReader,
        documents: DocumentStore,
        evidence: ProviderEvidenceStore,
        knowledge: AnalysisKnowledgeSource,
        payloads: AnalysisPayloadStore,
        provider: AIProvider | None,
    ):
        self.transactions = transactions
        self.analyses = analyses
        self.sources = sources
        self.documents = documents
        self.evidence = evidence
        self._knowledge = knowledge
        self.snapshot_payloads = payloads
        self._provider = provider
        self.activation = AnalysisActivation(analyses, sources, documents)

    @staticmethod
    def refuse_deleted(application_id: str, deleted_at: str | None) -> None:
        if deleted_at is not None:
            raise StateConflict(f"application is deleted: {application_id}")

    def snapshot_source(self, application_id: str, job_snapshot_id: str) -> AnalysisSnapshotSource:
        with self.transactions.read() as tx:
            source = self.sources.analysis_source(tx, job_snapshot_id)
        if source.application_id != application_id:
            raise LineageBroken(
                f"job snapshot {job_snapshot_id} does not belong to application {application_id}"
            )
        return source

    def analysis_context_source(
        self, application_id: str, job_analysis_id: str
    ) -> AnalysisContextSource:
        with self.transactions.read() as tx:
            source = self.sources.analysis_context_source(tx, job_analysis_id)
        if source.application_id != application_id:
            raise LineageBroken(
                f"job analysis {job_analysis_id} does not belong to application {application_id}"
            )
        return source

    def current_document(self, application_id: str) -> CVDocument | None:
        with self.transactions.read() as tx:
            return self.documents.document(tx, application_id)

    def document_source(self, application_id: str) -> DocumentSource:
        with self.transactions.read() as tx:
            return read_document_source(tx, self.documents, self.sources, application_id)

    def load_knowledge(self) -> Knowledge:
        return load_knowledge(self._knowledge)

    @staticmethod
    def assert_provider_io_allowed() -> None:
        assert_external_io_allowed("analysis provider execution")

    @property
    def provider(self) -> AIProvider:
        if self._provider is None:
            raise ProviderNotConfigured("AI mode was requested but no provider is configured")
        return self._provider

    def preserve(
        self,
        application_id: str,
        operation_id: str,
        task: str,
        provenance: ProviderTaskResult,
    ) -> ProviderEvidence:
        assert_external_io_allowed("provider response preservation")
        with self.transactions.read() as tx:
            response = self.evidence.find_response(
                tx, application_id, operation_id, task, provenance
            )
        if response is None:
            artifact_version_id = new_id()
            try:
                payload = self.snapshot_payloads.commit_provider_response(
                    application_id,
                    operation_id,
                    artifact_version_id,
                    provenance.sanitized_response,
                )
            except (OSError, ValueError) as exc:
                raise InfrastructureFailure(
                    f"could not preserve the provider response: {exc}"
                ) from exc
            response = StoredProviderResponse(artifact_version_id, payload)
        if (
            self.snapshot_payloads.verify_payload(
                response.payload.reference, response.payload.sha256
            )
            != "ok"
        ):
            raise InfrastructureFailure("preserved provider response failed payload verification")
        with self.transactions.write() as tx:
            registered = self.evidence.register_inactive(
                tx,
                application_id,
                operation_id,
                task,
                provenance,
                response,
            )
        if registered != response:
            if (
                self.snapshot_payloads.verify_payload(
                    registered.payload.reference, registered.payload.sha256
                )
                != "ok"
            ):
                raise InfrastructureFailure(
                    "preserved provider response failed payload verification"
                )
        response = registered
        return ProviderEvidence(task, response.artifact_version_id, response.payload, provenance)

    def prepare(
        self, command: AnalyzeCommand, *, operation_id: str | None = None
    ) -> PreparedAnalysis:
        assert_external_io_allowed("analysis preparation")
        return AnalysisPreparation.prepare(self, command, operation_id=operation_id)

    def activate(self, command: AnalyzeCommand, prepared: PreparedAnalysis) -> AnalysisResult:
        with self.transactions.write() as tx:
            return self.activation.activate(tx, command, prepared)

    def apply_analysis_decisions(
        self, command: ApplyAnalysisDecisionsCommand
    ) -> AnalysisDecisionsResult:
        return AnalysisCorrection.apply_analysis_decisions(self, command)
