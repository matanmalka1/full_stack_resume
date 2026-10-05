from __future__ import annotations

from collections.abc import Callable

from ....domain.contracts.document import CVDocument
from ....domain.knowledge import Knowledge
from ...commands import (
    AnalysisDecisionsResult,
    AnalysisResult,
    AnalyzeCommand,
    ApplyAnalysisDecisionsCommand,
)
from ...errors import LineageBroken, ProviderNotConfigured, StateConflict
from ...ports import AIProvider, TransactionManager
from ...ports.analysis_plans import (
    AnalysisContextSource,
    AnalysisContextSourceReader,
    AnalysisJobTextSource,
    AnalysisKnowledgeSource,
)
from ...ports.documents import DocumentStore
from ...transactions import assert_external_io_allowed
from ..ai_calls import AICallRunner
from ..documents import DocumentSource, load_knowledge, read_document_source
from .activation import AnalysisActivation
from .correction import AnalysisCorrection
from .preparation import AnalysisPreparation, PreparedAnalysis


class AnalysisService:
    """Own preparation scopes and synchronous analysis transaction boundaries."""

    def __init__(
        self,
        *,
        transactions: TransactionManager,
        activation: AnalysisActivation,
        sources: AnalysisContextSourceReader,
        documents: DocumentStore,
        ai_calls: AICallRunner,
        knowledge: AnalysisKnowledgeSource,
        provider: AIProvider | None,
    ):
        self.transactions = transactions
        self.activation = activation
        self.sources = sources
        self.documents = documents
        self.ai_calls = ai_calls
        self._knowledge = knowledge
        self._provider = provider

    @staticmethod
    def refuse_deleted(application_id: str, deleted_at: str | None) -> None:
        if deleted_at is not None:
            raise StateConflict(f"application is deleted: {application_id}")

    def job_text_source(self, application_id: str, job_text_hash: str) -> AnalysisJobTextSource:
        """The Application's job text, refused unless it is still the text the caller read."""
        with self.transactions.read() as tx:
            source = self.sources.job_text_source(tx, application_id)
        if source.job_text_hash != job_text_hash:
            raise StateConflict(
                "the job text changed since it was read (job_text_hash): "
                f"expected {job_text_hash}, found {source.job_text_hash}"
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

    def prepare(
        self,
        command: AnalyzeCommand,
        *,
        operation_id: str | None = None,
        still_owned: Callable[[], bool] = lambda: True,
    ) -> PreparedAnalysis:
        assert_external_io_allowed("analysis preparation")
        return AnalysisPreparation.prepare(
            self, command, operation_id=operation_id, still_owned=still_owned
        )

    def activate(self, command: AnalyzeCommand, prepared: PreparedAnalysis) -> AnalysisResult:
        with self.transactions.write() as tx:
            return self.activation.activate(tx, command, prepared)

    def apply_analysis_decisions(
        self, command: ApplyAnalysisDecisionsCommand
    ) -> AnalysisDecisionsResult:
        return AnalysisCorrection.apply_analysis_decisions(self, command)
