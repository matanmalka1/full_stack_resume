from __future__ import annotations

from datetime import date

from ....domain.contracts.recruitment import ApplicationStatus
from ....domain.document import basis, content_check, preparation_state
from ....domain.recruitment import user_transition_targets
from ...errors import (
    # Re-exported: the API and test suite catch WorkflowError from here, and
    # it is bound to the taxonomy's base class, so every refusal below is caught.
    InfrastructureFailure,
    KnowledgeRejected,
    UnknownRecord,
)
from ...ports.application_projections import ApplicationProjectionReader
from ...ports.documents import DocumentStore, DocumentSubmissionStore
from ...ports.outbound import KnowledgeStore, SnapshotPayloadStore
from ...ports.transactions import ReadTransaction, TransactionManager
from ...queries import (
    ApplicationDetailView,
    ApplicationListQuery,
    ApplicationListView,
    DocumentView,
    SubmissionsView,
    analysis_view,
    application_list_item_view,
    application_view,
    document_view,
    narrow_application_list,
    recruitment_timeline_view,
    snapshot_view,
    submission_view,
)
from ...queries.views_prep import JobSnapshotHistoryItem, JobSnapshotHistoryView
from ...state import ProjectionContext, project_application_state


class ApplicationQueryService:
    """Storage-neutral read projections for the API and its clients.

    Every projection captures its database inputs - including the CV document the
    basis is computed from - in one read transaction; Knowledge is loaded before it,
    outside any database scope.
    """

    def __init__(
        self,
        *,
        transactions: TransactionManager,
        projections: ApplicationProjectionReader,
        documents: DocumentStore,
        submissions: DocumentSubmissionStore,
        knowledge: KnowledgeStore,
        payloads: SnapshotPayloadStore,
    ):
        self._transactions = transactions
        self._projections = projections
        self._documents = documents
        self._submissions = submissions
        self._knowledge = knowledge
        self.snapshot_payloads = payloads

    def load_knowledge(self):
        try:
            return self._knowledge.load()
        except OSError as exc:
            raise InfrastructureFailure(f"could not read Knowledge: {exc}") from exc
        except ValueError as exc:
            raise KnowledgeRejected(str(exc)) from exc

    def fact_store(self):
        try:
            return self._knowledge.facts()
        except OSError as exc:
            raise InfrastructureFailure(f"could not read facts: {exc}") from exc
        except ValueError as exc:
            raise KnowledgeRejected(str(exc)) from exc

    def job_snapshot_history(self, application_id: str) -> JobSnapshotHistoryView:
        with self._transactions.read() as transaction:
            self._projections.application(transaction, application_id)
            active = self._projections.latest_snapshot(transaction, application_id)
            records = self._projections.snapshots(transaction, application_id)
        items = []
        for record in records:
            try:
                text = self.snapshot_payloads.read_snapshot(
                    record["payload_path"], record["source_hash"]
                )
            except (OSError, ValueError):
                # Missing, unreadable or unverified content is never reconstructed.
                text = None
            items.append(
                JobSnapshotHistoryItem(
                    id=record["id"],
                    version_number=record["version_number"],
                    captured_at=record["captured_at"],
                    source_url=record.get("source_url"),
                    job_text=text,
                )
            )
        return JobSnapshotHistoryView(active_job_snapshot_id=active["id"], items=items)

    def _state_inputs(self, transaction: ReadTransaction, application_record, knowledge):
        application_id = application_record["id"]
        snapshot_record = self._projections.latest_snapshot(transaction, application_id)
        analyses = self._projections.analyses(transaction, application_id)
        context = ProjectionContext(
            application=application_record,
            active_job_snapshot_id=snapshot_record["id"],
            analyses=tuple(analyses),
            document=self._documents.document(transaction, application_id),
            knowledge=knowledge,
            today=date.today(),
            active_operation=self._projections.active_operation(transaction, application_id),
            latest_operation=self._projections.latest_operation(transaction, application_id),
            matching_context_operation_active=(
                self._projections.has_active_matching_context_operation(transaction, application_id)
            ),
        )
        return context, snapshot_record, analyses

    def list_applications(self, query: ApplicationListQuery | None = None) -> ApplicationListView:
        """One page of the Application list, narrowed and ordered by `query`.

        The projection is computed for every record before the query is applied:
        `preparation_state` is derived from the document and the basis, not stored,
        so there is nothing to filter, order, or page by until it exists.
        """
        knowledge = self.load_knowledge()
        try:
            with self._transactions.read() as transaction:
                captured = []
                for row in self._projections.applications(transaction):
                    context, _snapshot, analyses = self._state_inputs(transaction, row, knowledge)
                    captured.append((row, context, analyses))
            items = []
            for row, context, analyses in captured:
                state = project_application_state(context)
                latest = analyses[-1]["analysis"] if analyses else None
                items.append(application_list_item_view(row, state, latest))
            return narrow_application_list(items, query or ApplicationListQuery())
        except (TypeError, ValueError) as exc:
            raise InfrastructureFailure(f"stored application projection is invalid: {exc}") from exc

    def application_detail(self, application_id: str) -> ApplicationDetailView:
        knowledge = self.load_knowledge()
        try:
            with self._transactions.read() as transaction:
                application_record = self._projections.application(transaction, application_id)
                context, snapshot_record, analyses = self._state_inputs(
                    transaction, application_record, knowledge
                )
                application = application_view(
                    application_record, analyses[-1]["analysis"] if analyses else None
                )
                latest = analysis_view(analyses[-1], knowledge.facts) if analyses else None
                timeline = recruitment_timeline_view(
                    self._projections.recruitment_events(transaction, application_id),
                    self._projections.submissions(transaction, application_id),
                    self._projections.audit_records(transaction, application_id),
                )
            state = project_application_state(context)
            snapshot = snapshot_view(
                snapshot_record,
                self.snapshot_payloads.read_snapshot(
                    snapshot_record["payload_path"], snapshot_record["source_hash"]
                ),
            )
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown application: {application_id}") from exc
        except (TypeError, ValueError) as exc:
            raise InfrastructureFailure(f"stored application detail is invalid: {exc}") from exc
        return ApplicationDetailView(
            **state.model_dump(mode="python"),
            application=application,
            latest_snapshot=snapshot,
            latest_analysis=latest,
            allowed_recruitment_transitions=list(
                user_transition_targets(ApplicationStatus(application.current_status))
            ),
            recruitment_timeline=timeline,
        )

    def document(self, application_id: str) -> DocumentView:
        """§20: the CV document with its token, states, report and candidate accounting."""
        knowledge = self.load_knowledge()
        with self._transactions.read() as tx:
            self._projections.application(tx, application_id)
            document = self._documents.document(tx, application_id)
            if document is None:
                raise UnknownRecord(f"application {application_id} has no CV document yet")
            analysis = self._projections.analysis(tx, document.analysis_id)["analysis"]
        current = basis(document, knowledge.facts.facts)
        return document_view(
            document,
            language=analysis.language,
            facts=knowledge.facts,
            preparation_state=preparation_state(document, current),
            content_check=content_check(document, current),
        )

    def submissions(self, application_id: str) -> SubmissionsView:
        """§20: every Submission with the content it sent and each file's checksum."""
        with self._transactions.read() as tx:
            self._projections.application(tx, application_id)
            records = self._submissions.submissions(tx, application_id)
        return SubmissionsView(items=[submission_view(record) for record in records])
