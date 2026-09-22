from __future__ import annotations

from dataclasses import replace
from datetime import date

from ....domain.contracts.drafts import WorkingDraft
from ....domain.contracts.recruitment import ApplicationStatus
from ....domain.recruitment import user_transition_targets
from ...artifacts import verify_artifact
from ...errors import (
    # Re-exported: the API and test suite catch WorkflowError from here, and
    # it is bound to the taxonomy's base class, so every refusal below is caught.
    InfrastructureFailure,
    KnowledgeRejected,
    UnknownRecord,
)
from ...ports.application_projections import ApplicationProjectionReader
from ...ports.outbound import KnowledgeStore, Renderer, RevisionPayloadStore
from ...ports.ready import ReadyEvidence, ReadyEvidenceReader
from ...ports.transactions import ReadTransaction, TransactionManager
from ...queries import (
    ApplicationDetailView,
    ApplicationListQuery,
    ApplicationListView,
    ApprovedRevisionView,
    ApprovedRevisionsView,
    ArtifactVersionDetailView,
    ArtifactVersionsView,
    DecisionRecordView,
    DraftPreviewView,
    SelectionPlanDetailView,
    ValidationRunView,
    WorkingDraftFactsView,
    WorkingDraftView,
    analysis_view,
    application_list_item_view,
    application_view,
    approved_revision_view,
    artifact_version_view,
    decision_view,
    draft_facts_view,
    draft_outline_view,
    narrow_application_list,
    recruitment_timeline_view,
    selection_plan_detail_view,
    snapshot_view,
)
from ...queries.views_prep import JobSnapshotHistoryItem, JobSnapshotHistoryView
from ...ready import qualify_ready_revision
from ...state import ProjectionContext, project_application_state


class ApplicationQueryService:
    """Storage-neutral read projections for the API and its clients."""

    def __init__(
        self,
        *,
        transactions: TransactionManager,
        projections: ApplicationProjectionReader,
        ready_evidence: ReadyEvidenceReader,
        knowledge: KnowledgeStore,
        renderer: Renderer,
        payloads: RevisionPayloadStore,
    ):
        self._transactions = transactions
        self._projections = projections
        self._ready_evidence = ready_evidence
        self._knowledge = knowledge
        self._renderer = renderer
        self.snapshot_payloads = payloads
        self.revision_payloads = payloads

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

    def candidate(self):
        return self.load_knowledge().candidate

    @property
    def renderer(self) -> Renderer:
        return self._renderer

    def _artifact_versions(self, application_id: str):
        with self._transactions.read() as tx:
            return self._projections.artifact_versions(tx, application_id)

    def _state_inputs(
        self,
        transaction: ReadTransaction,
        application_record,
        knowledge,
    ):
        application_id = application_record["id"]
        snapshot_record = self._projections.latest_snapshot(transaction, application_id)
        analyses = self._projections.analyses(transaction, application_id)
        active_analysis_record = next(
            (
                record
                for record in reversed(analyses)
                if record["job_snapshot_id"] == snapshot_record["id"]
            ),
            None,
        )
        active_analysis_id = (
            active_analysis_record["id"] if active_analysis_record is not None else None
        )
        latest_plan = self._projections.latest_selection_plan(transaction, application_id)
        active_plan = (
            latest_plan
            if latest_plan is not None and latest_plan.job_analysis_id == active_analysis_id
            else None
        )
        working = self._projections.active_working_draft(transaction, application_id)
        draft_plan = (
            self._projections.selection_plan(transaction, working.selection_plan_id)
            if working is not None
            else None
        )
        validation = (
            self._projections.latest_validation_for_working_draft(transaction, working.id)
            if working is not None
            else None
        )
        revisions = tuple(self._projections.approved_revisions(transaction, application_id))
        active_operation = self._projections.active_operation(transaction, application_id)
        latest_operation = self._projections.latest_operation(transaction, application_id)
        matching_context_operation_active = self._projections.has_active_matching_context_operation(
            transaction, application_id
        )
        context = ProjectionContext(
            application=application_record,
            active_job_snapshot_id=snapshot_record["id"],
            active_analysis_id=active_analysis_id,
            active_analysis=(
                active_analysis_record["analysis"] if active_analysis_record is not None else None
            ),
            active_selection_plan=active_plan,
            draft_selection_plan=draft_plan,
            active_working_draft=working,
            latest_validation=validation,
            approved_revisions=revisions,
            ready_revision_ids=frozenset(),
            knowledge=knowledge,
            today=date.today(),
            active_operation=active_operation,
            latest_operation=latest_operation,
            matching_context_operation_active=matching_context_operation_active,
        )
        return context, snapshot_record, analyses

    def _ready_ids(self, evidence: list[ReadyEvidence], application_id: str) -> frozenset[str]:
        return frozenset(
            item.revision.id
            for item in evidence
            if qualify_ready_revision(self.revision_payloads, item, application_id).ready_qualified
        )

    def list_applications(self, query: ApplicationListQuery | None = None) -> ApplicationListView:
        """One page of the Application list, narrowed and ordered by `query`.

        The projection is computed for every record before the query is applied.
        It has to be: `preparation_state` is derived from a record's snapshots,
        drafts, validations, and revisions rather than stored on it, so there is
        nothing to filter, order, or page by until it exists. That makes paging a
        window on the answer rather than a way to read less of the database - it
        bounds what crosses the boundary and what a client renders, which is what
        the list screen needs from it.
        """
        knowledge = self.load_knowledge()
        try:
            with self._transactions.read() as transaction:
                captured = []
                for row in self._projections.applications(transaction):
                    context, _, analyses = self._state_inputs(transaction, row, knowledge)
                    evidence = [
                        self._ready_evidence.load(transaction, row["id"], revision.id)
                        for revision in context.approved_revisions
                    ]
                    captured.append((row, context, analyses, evidence))
            items = []
            for row, context, analyses, evidence in captured:
                ready_ids = self._ready_ids(evidence, row["id"])
                state = project_application_state(replace(context, ready_revision_ids=ready_ids))
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
                evidence = [
                    self._ready_evidence.load(transaction, application_id, revision.id)
                    for revision in context.approved_revisions
                ]
                application = application_view(
                    application_record, analyses[-1]["analysis"] if analyses else None
                )
                latest = analysis_view(analyses[-1], knowledge.facts) if analyses else None
                timeline = recruitment_timeline_view(
                    self._projections.recruitment_events(transaction, application_id),
                    self._projections.submissions(transaction, application_id),
                    self._projections.audit_records(transaction, application_id),
                )
            state = project_application_state(
                replace(
                    context,
                    ready_revision_ids=self._ready_ids(evidence, application_id),
                )
            )
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

    def artifact_versions(self, application_id: str) -> ArtifactVersionsView:
        try:
            with self._transactions.read() as tx:
                self._projections.application(tx, application_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown application: {application_id}") from exc
        try:
            return ArtifactVersionsView(
                items=[
                    artifact_version_view(row) for row in self._artifact_versions(application_id)
                ]
            )
        except (TypeError, ValueError) as exc:
            raise InfrastructureFailure(f"stored artifact projection is invalid: {exc}") from exc

    def artifact_version(self, artifact_version_id: str) -> ArtifactVersionDetailView:
        """§20: one registered artifact's metadata and its download eligibility.

        By ID, like every other artifact surface. The stored path is read here
        and handed straight to the verification port; it never reaches the view,
        which is why the view and the detail view are the same field set plus
        three answers about availability.
        """
        try:
            with self._transactions.read() as tx:
                record = self._projections.artifact_version(tx, artifact_version_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown artifact version: {artifact_version_id}") from exc
        try:
            view = artifact_version_view(record)
        except (TypeError, ValueError) as exc:
            raise InfrastructureFailure(f"stored artifact projection is invalid: {exc}") from exc
        availability = verify_artifact(self.revision_payloads, view, record["path"])
        return ArtifactVersionDetailView(
            **view.model_dump(mode="python"),
            downloadable=availability.downloadable,
            size=availability.size,
            unavailable_reason=availability.reason,
        )

    def approved_revision(self, approved_revision_id: str) -> ApprovedRevisionView:
        """§20: one ApprovedRevision with its Ready qualification re-derived.

        The qualification is computed here rather than read, and it is computed
        for this exact revision rather than for the Application's latest one, so
        a superseded revision reports its own truth: still qualified, still
        exportable, and no longer the active milestone.
        """
        try:
            with self._transactions.read() as tx:
                revision = self._projections.approved_revision(tx, approved_revision_id)
                evidence = self._ready_evidence.load(tx, revision.application_id, revision.id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown approved revision: {approved_revision_id}") from exc
        qualification = qualify_ready_revision(
            self.revision_payloads, evidence, revision.application_id
        )
        return approved_revision_view(revision, qualification)

    def approved_revisions(self, application_id: str) -> ApprovedRevisionsView:
        """All immutable revisions for one Application, each with its own qualification."""
        try:
            with self._transactions.read() as tx:
                self._projections.application(tx, application_id)
                revisions = self._projections.approved_revisions(tx, application_id)
                evidence = [
                    self._ready_evidence.load(tx, application_id, revision.id)
                    for revision in revisions
                ]
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown application: {application_id}") from exc

        try:
            return ApprovedRevisionsView(
                items=[
                    approved_revision_view(
                        revision,
                        qualify_ready_revision(self.revision_payloads, item, application_id),
                    )
                    for revision, item in zip(revisions, evidence, strict=True)
                ]
            )
        except (TypeError, ValueError) as exc:
            raise InfrastructureFailure(
                f"stored approved revision projection is invalid: {exc}"
            ) from exc

    def working_draft(self, working_draft_id: str) -> WorkingDraftView:
        """§20: one WorkingDraft by ID, with the token a client conditions on.

        Read by ID rather than by Application: the client that is about to
        `PATCH` one has to name the draft it is editing, and a read that
        resolved `latest` for it could hand back a different draft than the one
        the ETag it then sends was taken from.
        """
        with self._transactions.read() as tx:
            working = self._projections.working_draft(tx, working_draft_id)
            latest = self._projections.latest_validation_for_working_draft(tx, working_draft_id)
        exact = (
            latest
            if latest is not None
            and latest["edit_version"] == working.edit_version
            and latest["content_hash"] == working.content_hash
            else None
        )
        return WorkingDraftView(
            **working.model_dump(mode="python"),
            outline=draft_outline_view(working.source),
            latest_validation_run_id=exact["id"] if exact else None,
            latest_validation_passed=exact["report"].passed if exact else None,
        )

    def selection_plan(self, selection_plan_id: str) -> SelectionPlanDetailView:
        """§20: one immutable plan plus every fact candidate the decision ranked."""

        try:
            with self._transactions.read() as tx:
                plan = self._projections.selection_plan(tx, selection_plan_id)
                analysis_record = self._projections.analysis(tx, plan.job_analysis_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown selection plan: {selection_plan_id}") from exc
        try:
            return selection_plan_detail_view(
                plan,
                self.fact_store(),
                analysis_record["analysis"].language,
            )
        except (TypeError, ValueError) as exc:
            raise InfrastructureFailure(f"stored selection plan detail is invalid: {exc}") from exc

    def validation_run(self, validation_run_id: str) -> ValidationRunView:
        with self._transactions.read() as tx:
            record = self._projections.validation_run(tx, validation_run_id)
        report = record["report"]
        return ValidationRunView(
            application_id=record["application_id"],
            working_draft_id=record["working_draft_id"],
            validation_run_id=record["id"],
            edit_version=record["edit_version"],
            content_hash=record["content_hash"],
            passed=report.passed,
            report=report,
            created_at=record["created_at"],
        )

    def _working_draft(self, working_draft_id: str) -> WorkingDraft:
        try:
            with self._transactions.read() as tx:
                return self._projections.working_draft(tx, working_draft_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown working draft: {working_draft_id}") from exc

    def working_draft_facts(self, working_draft_id: str) -> WorkingDraftFactsView:
        """§20 candidate accounting for one draft, in the draft's own language.

        Read here rather than derived in a client: the fact renderings are
        Knowledge, and a browser that had to name facts by ID could only show
        the identifiers the M4 gate says a user must never need.
        """
        working = self._working_draft(working_draft_id)
        return draft_facts_view(
            working.id,
            working.application_id,
            working.selection_plan_id,
            working.source,
            self.fact_store(),
        )

    def working_draft_preview(self, working_draft_id: str) -> DraftPreviewView:
        """§20/architecture §13: this exact draft version rendered to HTML.

        The same composition the approved render uses, so what a user checks
        before approving is what the approval renders. No browser is started and
        nothing is written: a preview refreshes on every save, and neither
        belongs on that path.
        """
        working = self._working_draft(working_draft_id)
        return DraftPreviewView(
            working_draft_id=working.id,
            edit_version=working.edit_version,
            content_hash=working.content_hash,
            language=working.source.language,
            html=self.renderer.preview_html(working.source, self.candidate()),
        )

    def latest_decision(self, application_id: str) -> DecisionRecordView:
        try:
            with self._transactions.read() as tx:
                return decision_view(self._projections.latest_decision(tx, application_id))
        except UnknownRecord as exc:
            raise UnknownRecord(f"no decision record for application: {application_id}") from exc
        except (TypeError, ValueError) as exc:
            raise InfrastructureFailure(f"stored decision projection is invalid: {exc}") from exc
