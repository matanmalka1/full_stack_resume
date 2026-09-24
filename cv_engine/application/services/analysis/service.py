from __future__ import annotations

from ....domain.contracts.providers import ProviderTaskResult
from ....domain.contracts.selection import SelectionPlan
from ....domain.knowledge import Knowledge
from ....util import new_id
from ...commands import (
    AnalysisDecisionsResult,
    AnalysisResult,
    AnalyzeCommand,
    ApplyAnalysisDecisionsCommand,
    CreateSelectionPlanCommand,
    ProposeSelectionPlanCommand,
    SelectionPlanResult,
)
from ...errors import (
    InfrastructureFailure,
    KnowledgeRejected,
    LineageBroken,
    ProviderNotConfigured,
    StateConflict,
)
from ...ports import AIProvider, TransactionManager
from ...ports.analysis_plans import (
    AnalysisKnowledgeSource,
    AnalysisPayloadStore,
    AnalysisPlanStore,
    AnalysisSelectionSourceReader,
    AnalysisSnapshotSource,
    SelectionSource,
)
from ...ports.payload_leases import DEFAULT_LEASE_TTL_SECONDS, PayloadWriteLeaseStore
from ...ports.provider_evidence import ProviderEvidenceStore, StoredProviderResponse
from ...transactions import assert_external_io_allowed
from ..proposals import ProviderEvidence
from .activation import AnalysisActivation
from .correction import AnalysisCorrection
from .preparation import AnalysisPreparation, PreparedAnalysis
from .selection_plans import AnalysisSelectionService
from .selection_policy import PreparedSelectionPlan, PreparedSelectionProposal


def load_analysis_knowledge(source: AnalysisKnowledgeSource) -> Knowledge:
    try:
        return source.load()
    except OSError as exc:
        raise InfrastructureFailure(f"could not read Knowledge: {exc}") from exc
    except ValueError as exc:
        raise KnowledgeRejected(str(exc)) from exc


class AnalysisService:
    """Own preparation scopes and synchronous analysis/selection transaction boundaries."""

    def __init__(
        self,
        *,
        transactions: TransactionManager,
        plans: AnalysisPlanStore,
        sources: AnalysisSelectionSourceReader,
        evidence: ProviderEvidenceStore,
        knowledge: AnalysisKnowledgeSource,
        payloads: AnalysisPayloadStore,
        leases: PayloadWriteLeaseStore,
        provider: AIProvider | None,
    ):
        self.transactions = transactions
        self.plans = plans
        self.sources = sources
        self.evidence = evidence
        self._knowledge = knowledge
        self.snapshot_payloads = payloads
        self._leases = leases
        self._provider = provider
        self.activation = AnalysisActivation(plans, sources)

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

    def selection_source(self, application_id: str, job_analysis_id: str) -> SelectionSource:
        with self.transactions.read() as tx:
            source = self.sources.selection_source(tx, job_analysis_id)
        if source.application_id != application_id:
            raise LineageBroken(
                f"job analysis {job_analysis_id} does not belong to application {application_id}"
            )
        return source

    def selection_plan(self, selection_plan_id: str) -> SelectionPlan:
        with self.transactions.read() as tx:
            return self.plans.selection_plan(tx, selection_plan_id)

    def load_knowledge(self) -> Knowledge:
        return load_analysis_knowledge(self._knowledge)

    @staticmethod
    def assert_provider_io_allowed() -> None:
        assert_external_io_allowed("analysis/selection provider execution")

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
        lease_reference: str | None = None
        if response is None:
            artifact_version_id = new_id()
            # provider_path already embeds a freshly-minted artifact_version_id
            # per attempt, so - as with a JobSnapshot payload - the reference
            # serves as its own group key and attempt_id (architecture.md §7.1).
            reference = self.snapshot_payloads.reference_for(
                self.snapshot_payloads.provider_path(
                    application_id, operation_id, artifact_version_id
                )
            )
            with self.transactions.write() as tx:
                self._leases.acquire(
                    tx,
                    reference,
                    reference,
                    keys=[reference],
                    ttl_seconds=DEFAULT_LEASE_TTL_SECONDS,
                )
            try:
                payload = self.snapshot_payloads.commit_provider_response(
                    application_id,
                    operation_id,
                    artifact_version_id,
                    provenance.sanitized_response,
                )
            except (OSError, ValueError) as exc:
                with self.transactions.write() as tx:
                    self._leases.release(tx, reference, reference)
                raise InfrastructureFailure(
                    f"could not preserve the provider response: {exc}"
                ) from exc
            response = StoredProviderResponse(artifact_version_id, payload)
            lease_reference = reference
        if (
            self.snapshot_payloads.verify_payload(
                response.payload.reference, response.payload.sha256
            )
            != "ok"
        ):
            raise InfrastructureFailure("preserved provider response failed payload verification")
        with self.transactions.write() as tx:
            if lease_reference is not None:
                self._leases.mark_committed(
                    tx, lease_reference, lease_reference, keys=[lease_reference]
                )
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

    def prepare_selection_plan(self, command: CreateSelectionPlanCommand) -> PreparedSelectionPlan:
        assert_external_io_allowed("selection preparation")
        return AnalysisSelectionService.prepare_selection_plan(self, command)

    def create_selection_plan(self, command: CreateSelectionPlanCommand) -> SelectionPlanResult:
        prepared = self.prepare_selection_plan(command)
        with self.transactions.write() as tx:
            return self.activation.activate_selection_plan(tx, prepared)

    def prepare_selection_proposal(
        self,
        command: ProposeSelectionPlanCommand,
        *,
        operation_id: str,
    ) -> PreparedSelectionProposal:
        assert_external_io_allowed("selection provider preparation")
        return AnalysisSelectionService.prepare_selection_proposal(
            self, command, operation_id=operation_id
        )

    def apply_analysis_decisions(
        self, command: ApplyAnalysisDecisionsCommand
    ) -> AnalysisDecisionsResult:
        return AnalysisCorrection.apply_analysis_decisions(self, command)
