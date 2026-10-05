from __future__ import annotations

from datetime import date

from ....domain.contracts.recruitment import ApplicationStatus
from ....domain.document import basis, content_check, preparation_state
from ....domain.recruitment import user_transition_targets
from ...errors import (
    # Re-exported: the API and test suite catch WorkflowError from here, and
    # it is bound to the taxonomy's base class, so every refusal below is caught.
    InfrastructureFailure,
    UnknownRecord,
)
from ...ports.analysis_plans import AnalysisKnowledgeSource
from ...ports.application_projections import ApplicationProjectionReader
from ...ports.documents import DocumentStore, DocumentSubmissionStore
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
    job_posting_view,
    narrow_application_list,
    recruitment_timeline_view,
    submission_view,
)
from ...state import ProjectionContext, project_application_state
from ..documents import load_knowledge


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
        knowledge: AnalysisKnowledgeSource,
    ):
        self._transactions = transactions
        self._projections = projections
        self._documents = documents
        self._submissions = submissions
        self._knowledge = knowledge

    def load_knowledge(self):
        return load_knowledge(self._knowledge)

    def _state_inputs(self, transaction: ReadTransaction, application_record, knowledge):
        application_id = application_record["id"]
        analyses = self._projections.analyses(transaction, application_id)
        context = ProjectionContext(
            application=application_record,
            job_text_hash=application_record["job_text_hash"],
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
        return context, analyses

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
                    context, analyses = self._state_inputs(transaction, row, knowledge)
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
                context, analyses = self._state_inputs(transaction, application_record, knowledge)
                posting = job_posting_view(
                    application_record,
                    locked=self._projections.has_submission(transaction, application_id),
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
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown application: {application_id}") from exc
        except (TypeError, ValueError) as exc:
            raise InfrastructureFailure(f"stored application detail is invalid: {exc}") from exc
        return ApplicationDetailView(
            **state.model_dump(mode="python"),
            application=application,
            job_posting=posting,
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
