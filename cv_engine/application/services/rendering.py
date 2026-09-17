from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...domain.contracts.analysis import JobAnalysis
from ...domain.contracts.drafts import DraftDocument
from ...domain.contracts.knowledge import Profile
from ...domain.contracts.validation import (
    ReadyQualification,
    ValidationReport,
)
from ...domain.draft_markdown import parse_draft
from ...domain.knowledge import Knowledge
from ...domain.validation import validate_draft
from ...util import canonical_json, new_id, sha256_text
from ..artifacts import ArtifactDelivery, deliver_artifact
from ..chain import ChainError, DraftChainSources, check_loaded_draft_chain
from ..commands import (
    RenderCommand,
    RenderResult,
)
from ..errors import (
    # Re-exported: the API and test suite catch WorkflowError from here, and
    # it is bound to the taxonomy's base class, so every refusal below is caught.
    ApplicationError,
    InfrastructureFailure,
    LineageBroken,
    StateConflict,
    UnknownRecord,
    ValidationBlocked,
)
from ..operations import OperationSources
from ..ports import (
    KnowledgeStore,
    Renderer,
    RenderTargets,
    RevisionPayloadStore,
)
from ..ports.artifact_catalog import ArtifactCatalog
from ..ports.draft_lifecycle import DraftLifecycleStore
from ..ports.ready import ReadyEvidenceReader
from ..ports.rendering import RenderContextReader
from ..ports.transactions import TransactionManager, WriteTransaction
from ..ports.validation_store import ValidationStore
from ..queries import artifact_version_view
from ..ready import qualify_ready_revision


@dataclass(frozen=True)
class PreparedRender:
    command: RenderCommand
    knowledge: Knowledge
    draft: DraftDocument
    profile: Profile
    analysis: JobAnalysis
    source_report: ValidationReport
    manifest_record: dict[str, Any]
    artifact_ids: tuple[str, str]
    targets: RenderTargets


@dataclass(frozen=True)
class ExecutedRender:
    prepared: PreparedRender
    report: ValidationReport
    artifact_ids: tuple[str, str]


class RenderingService:
    """Rendering an approved revision and reporting ready state."""

    def __init__(
        self,
        *,
        transactions: TransactionManager,
        catalog: ArtifactCatalog,
        validations: ValidationStore,
        ready_evidence: ReadyEvidenceReader,
        contexts: RenderContextReader,
        drafts: DraftLifecycleStore,
        knowledge: KnowledgeStore,
        renderer: Renderer,
        payloads: RevisionPayloadStore,
    ):
        self._transactions = transactions
        self._catalog = catalog
        self._validations = validations
        self._ready_evidence = ready_evidence
        self._contexts = contexts
        self._drafts = drafts
        self._knowledge = knowledge
        self.renderer = renderer
        self.revision_payloads = payloads
        self.snapshot_payloads = payloads

    def load_knowledge(self) -> Knowledge:
        try:
            return self._knowledge.load()
        except OSError as exc:
            raise InfrastructureFailure(f"could not read Knowledge: {exc}") from exc

    def _registered_draft(self, reference: str) -> DraftDocument:
        """Load one approved claim manifest through immutable payload storage."""
        try:
            return parse_draft(self._registered_text(reference))
        except (OSError, ValueError) as exc:
            raise InfrastructureFailure(f"could not load stored draft: {exc}") from exc

    def _registered_text(self, reference: str) -> str:
        """Read one registered immutable payload as text."""
        try:
            return self.snapshot_payloads.read_payload_text(reference)
        except OSError as exc:
            raise InfrastructureFailure(f"could not read stored artifact: {exc}") from exc

    @staticmethod
    def _markdown_reference_beside(manifest_reference: str) -> str:
        """Derive the approved Markdown reference beside its claim manifest."""
        head, _, tail = manifest_reference.rpartition("/")
        if tail != "resume.json" or not head:
            raise InfrastructureFailure(
                f"claim manifest is not an approved revision payload: {manifest_reference}"
            )
        return f"{head}/resume.md"

    def render(self, application_id: str) -> RenderResult:
        try:
            with self._transactions.read() as tx:
                deleted_at = self._contexts.application_deleted_at(tx, application_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown application: {application_id}") from exc
        if deleted_at is not None:
            raise StateConflict(f"application is deleted: {application_id}")
        try:
            with self._transactions.read() as tx:
                revision_id = self._drafts.latest_approved_revision(tx, application_id).id
        except UnknownRecord as exc:
            raise UnknownRecord(f"no approved revision for application: {application_id}") from exc
        command = RenderCommand(
            application_id=application_id,
            approved_revision_id=revision_id,
        )
        prepared = self.prepare(command)
        executed = self.execute(prepared)
        with self._transactions.write() as tx:
            result = self.activate(tx, executed)
        self.verify_activation(executed)
        return result

    def freeze_operation_sources(
        self, command: RenderCommand, knowledge_context_hash: str
    ) -> OperationSources:
        with self._transactions.read() as tx:
            context = self._contexts.operation_sources(tx, command.approved_revision_id)
        revision = context.revision
        if revision.application_id != command.application_id:
            raise LineageBroken("approved revision does not belong to the named Application")
        return OperationSources(
            job_snapshot_id=revision.job_snapshot_id,
            job_snapshot_hash=context.snapshot["source_hash"],
            job_analysis_id=revision.job_analysis_id,
            selection_plan_id=revision.selection_plan_id,
            approved_revision_id=revision.id,
            knowledge_context_hash=knowledge_context_hash,
            dependency_hashes={
                "approved_revision": sha256_text(canonical_json(revision.model_dump(mode="json"))),
                "claim_manifest": context.manifest["content_hash"],
            },
        )

    def operation_source_payloads_match(self, revision_id: str) -> bool:
        """Verify immutable render inputs without holding a database transaction."""
        with self._transactions.read() as tx:
            context = self._contexts.operation_sources(tx, revision_id)
        expected = (
            (context.manifest["path"], context.manifest["content_hash"]),
            (context.revision.resume_markdown_reference, context.revision.resume_markdown_hash),
        )
        return all(
            self.revision_payloads.verify_payload(reference, content_hash) == "ok"
            for reference, content_hash in expected
        )

    def prepare(self, command: RenderCommand) -> PreparedRender:
        knowledge = self.load_knowledge()
        facts, profiles, policies = knowledge.facts, knowledge.profiles, knowledge.policies
        try:
            with self._transactions.read() as tx:
                context = self._contexts.operation_sources(tx, command.approved_revision_id)
            revision = context.revision
            manifest_record = context.manifest
        except UnknownRecord as exc:
            raise UnknownRecord(
                f"unknown approved revision: {command.approved_revision_id}"
            ) from exc
        if revision.application_id != command.application_id:
            raise LineageBroken("approved revision does not belong to the named Application")
        # The claim manifest and the approved Markdown beside it are registered
        # immutable payloads, so they are read through the store rather than
        # resolved to a local path. Resolving them worked only while storage
        # happened to be the same disk the application sits on.
        manifest_reference = manifest_record["path"]
        draft = self._registered_draft(manifest_reference)
        profile = profiles.get(draft.profile)
        chain = check_loaded_draft_chain(
            DraftChainSources(
                context.analysis, context.snapshot, context.latest_snapshot_id, context.analyses
            ),
            command.application_id,
            draft,
            profiles,
            facts,
            recorded_analysis_id=context.decision["job_analysis_id"],
        )
        try:
            _, analysis = chain.bound()
        except ChainError as exc:
            raise LineageBroken(f"draft chain rejected: {exc}") from exc
        source_report = validate_draft(
            draft,
            self._registered_text(self._markdown_reference_beside(manifest_reference)),
            facts,
            profile,
            analysis,
            plan=context.plan,
            policies=policies,
            presentations=knowledge.presentations,
        )
        with self._transactions.write() as tx:
            self._validations.record_validation(
                tx, command.application_id, "approved-source-pre-render", source_report
            )
        if not source_report.passed:
            raise ValidationBlocked(
                "render blocked because the approved Markdown no longer matches its validated claims",
                source_report,
            )
        candidate = knowledge.candidate
        artifact_ids = (new_id(), new_id())
        recruiter_pdf_filename = self.renderer.filename_for(profile.normalized_role, candidate)
        targets = self.revision_payloads.render_targets(
            command.application_id,
            command.approved_revision_id,
            artifact_ids[0],
            artifact_ids[1],
            recruiter_pdf_filename,
        )
        return PreparedRender(
            command=command,
            knowledge=knowledge,
            draft=draft,
            profile=profile,
            analysis=analysis,
            source_report=source_report,
            manifest_record=manifest_record,
            artifact_ids=artifact_ids,
            targets=targets,
        )

    def execute(self, prepared: PreparedRender) -> ExecutedRender:
        draft = prepared.draft
        candidate = prepared.knowledge.candidate
        targets = prepared.targets
        html_path, pdf_path = targets.html, targets.pdf
        try:
            self.renderer.render_html(draft, html_path, candidate)
            geometry = self.renderer.render_pdf(html_path, pdf_path)
            report = self.renderer.validate_rendered(
                draft,
                prepared.profile,
                html_path,
                pdf_path,
                geometry,
                candidate,
                targets.recruiter_pdf_filename,
            )
        except FileExistsError as exc:
            raise StateConflict(str(exc)) from exc
        except ApplicationError:
            raise
        except (OSError, RuntimeError) as exc:
            raise InfrastructureFailure(f"rendering failed: {exc}") from exc
        artifact_ids = self._register_outputs(prepared, report)
        return ExecutedRender(prepared=prepared, report=report, artifact_ids=artifact_ids)

    def _register_outputs(
        self, prepared: PreparedRender, report: ValidationReport
    ) -> tuple[str, str]:
        """Register the two rendered artifacts, in the execute phase.

        **Not at activation.** The Operation runner records this render's two
        outputs as soon as `execute` returns and *before* it re-checks
        cancellation, using the IDs `prepare` reserved. Registering the matching
        `artifact_versions` rows inside the activation transaction meant that a
        render cancelled - or overtaken by a source change - in the window
        between the two phases ended with Operation outputs naming rows
        that were never written. `operation_outputs.output_id` carries no
        foreign key, so nothing in the schema refused it and nothing reading the
        Operation could tell the dangling references from real ones.

        Product specification §18 requires the opposite: a completed output
        after cancellation is recorded as inactive evidence. A reference to
        nothing is not evidence. So the row is written in the same phase as the
        file it points at, and *activation* stays where §6 invariant 15 puts it -
        on the Operation output's `active` flag, which the runner sets only
        inside a successful commit. Output existence and output activation are
        separate, and this is the seam where they separate.

        This is the same repair the AI tasks took in Stage G, in the mirror
        image: there a payload existed with no row naming it, here a row named
        something that did not exist.

        Written outside the *activation* transaction, in its own short token-owned write scope.
        Both halves of that matter and they pull in opposite directions:

        - Not the activation transaction, because a row committed only alongside
          the outcome does not exist when there is no outcome. That is the
          orphan this repair exists to remove.
        - Still one transaction, because both artifacts are one render. Left as
          independent writes, a failure on the second would leave one row
          committed while `execute` raised - so the runner would
          record no Operation output at all, and the Application would carry
          registered artifacts belonging to a render that never reported. Half a
          render's evidence is not evidence, and "it survives cancellation" is a
          weaker claim than "it is all there or none of it is".


        """
        command = prepared.command
        draft = prepared.draft
        targets = prepared.targets
        lifecycle = "rendered" if report.passed else "rendered-invalid"
        stored_outputs = []
        for artifact_version_id, artifact_type, path in [
            (prepared.artifact_ids[0], "resume_html", targets.html),
            (prepared.artifact_ids[1], "resume_pdf", targets.pdf),
        ]:
            stored_outputs.append(
                (
                    artifact_version_id,
                    artifact_type,
                    self.revision_payloads.ingest_render_output(path),
                )
            )
        with self._transactions.write() as tx:
            final_ids = []
            for artifact_version_id, artifact_type, stored in stored_outputs:
                existing = self._contexts.matching_render_artifact(
                    tx, command.approved_revision_id, artifact_type, stored.sha256, lifecycle
                )
                if existing is not None:
                    final_ids.append(existing["id"])
                    continue
                metadata: dict[str, Any] = {"validation_passed": report.passed}
                if artifact_type == "resume_pdf":
                    metadata["recruiter_filename"] = targets.recruiter_pdf_filename
                # The rendered file enters storage here, and the row records
                # what storage returned. Deriving the reference from the path
                # and hashing the file separately described two different
                # reads of the same location; one ingest describes one.
                registered_id = self._catalog.register_artifact_version(
                    tx,
                    command.application_id,
                    artifact_type,
                    "resume",
                    stored.reference,
                    stored.sha256,
                    lifecycle,
                    revision_id=command.approved_revision_id,
                    job_snapshot_id=draft.job_snapshot_id,
                    track=draft.track.value,
                    profile=draft.profile.value,
                    emphasis=draft.emphasis.value,
                    facts_version=prepared.knowledge.facts.version,
                    approved_at=prepared.manifest_record["approved_at"],
                    metadata=metadata,
                    artifact_version_id=artifact_version_id,
                )
                if registered_id != artifact_version_id:
                    raise InfrastructureFailure(
                        "artifact registry did not preserve the reserved output identity"
                    )
                final_ids.append(registered_id)
        return final_ids[0], final_ids[1]

    def activate(
        self,
        tx: WriteTransaction,
        executed: ExecutedRender,
    ) -> RenderResult:
        prepared = executed.prepared
        command = prepared.command
        report = executed.report
        artifact_ids = executed.artifact_ids
        # Both artifact versions already exist: `execute` registered them
        # beside the files they point at, so a cancellation between the phases
        # leaves inactive evidence rather than dangling references. What belongs
        # here is only what activation means - the post-render ValidationRun that
        # binds this report to the exact PDF, and the Ready qualification.
        self._validations.record_validation(
            tx, command.application_id, "post-render", report, artifact_ids[1]
        )
        return RenderResult(
            application_id=command.application_id,
            pdf_artifact_version_id=artifact_ids[1],
            validation=report,
        )

    def verify_activation(self, executed: ExecutedRender) -> None:
        if not executed.report.passed:
            return
        prepared = executed.prepared
        qualification = self.ready_qualification(
            prepared.command.application_id,
            prepared.command.approved_revision_id,
            executed.artifact_ids[1],
        )
        if not qualification.ready_qualified:
            raise ValidationBlocked(
                "render succeeded but fresh ready integrity verification failed: "
                f"{[issue.code for issue in qualification.validation.issues]}"
            )

    def download_artifact(self, artifact_version_id: str) -> ArtifactDelivery:
        """§20/§12: one registered artifact, addressed by ID and nothing else.

        There is no path argument and no `latest`. An ID that is registered
        nowhere is `UnknownRecord`, which is what a traversal string arriving in
        the path segment turns into: an identifier that names no row. An ID that
        *is* registered but whose payload fails containment, presence, or its
        hash is a different refusal, raised by the store, because a record that
        exists and does not verify is not the same finding as one that never
        existed.

        Ready qualification is deliberately not required. This serves the HTML
        preview, the approved Markdown, and the archived draft
        snapshots - none of which are the Ready PDF, and none of which become
        readable only once a revision qualifies. The one export that does
        require qualification is `export_recruiter_pdf`, and it says so.
        """
        record = self._artifact_record(artifact_version_id)
        return deliver_artifact(
            self.revision_payloads, artifact_version_view(record), record["path"]
        )

    def export_recruiter_pdf(
        self,
        approved_revision_id: str,
        pdf_artifact_version_id: str,
    ) -> ArtifactDelivery:
        """§16: the exact Ready PDF, under its recruiter-facing name.

        Both IDs are explicit and both are checked against each other, so an
        export cannot be satisfied by whatever PDF happens to be newest. The
        four verifications §16 names happen in this order: registration, then
        that the named PDF is this revision's rendered PDF, then Ready
        qualification of that exact pair, then - inside the store - hash and
        containment.

        Active-context compatibility is deliberately not checked. §16 says so
        directly, and it is the property that makes a superseded revision still
        exportable: a new JobSnapshot removes a revision from the active
        PreparationState, but it does not unmake the evidence that the revision
        rendered and qualified.
        """
        record = self._artifact_record(pdf_artifact_version_id)
        try:
            with self._transactions.read() as tx:
                revision = self._drafts.approved_revision(tx, approved_revision_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown approved revision: {approved_revision_id}") from exc
        if record["artifact_type"] != "resume_pdf":
            raise LineageBroken(f"artifact {pdf_artifact_version_id} is not a rendered PDF")
        if record["revision_id"] != revision.id:
            raise LineageBroken("the named PDF does not belong to the named approved revision")
        qualification = self.ready_qualification(
            revision.application_id, revision.id, pdf_artifact_version_id
        )
        if not qualification.ready_qualified:
            raise ValidationBlocked(
                "this approved revision is not Ready-qualified, so its PDF is not exportable",
                qualification.validation,
            )
        # No `filename=` override. The recruiter name is the one render wrote
        # into this artifact's registration; recomputing it here would invent a
        # name at export time that the immutable record never carried, and would
        # make an export depend on a renderer being configured at all.
        return deliver_artifact(
            self.revision_payloads, artifact_version_view(record), record["path"]
        )

    def preview_approved_html(
        self, approved_revision_id: str, html_artifact_version_id: str
    ) -> ArtifactDelivery:
        """Return one verified rendered HTML artifact bound to one revision.

        Presence, containment, and hash verification remain in `download_artifact`;
        this method adds only the lineage/type checks required by the revision route.
        """
        record = self._artifact_record(html_artifact_version_id)
        try:
            with self._transactions.read() as tx:
                revision = self._drafts.approved_revision(tx, approved_revision_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown approved revision: {approved_revision_id}") from exc
        if record["artifact_type"] != "resume_html" or record["lifecycle_status"] != "rendered":
            raise LineageBroken(f"artifact {html_artifact_version_id} is not rendered resume HTML")
        if record["revision_id"] != revision.id:
            raise LineageBroken("the named HTML does not belong to the named approved revision")
        if record["application_id"] != revision.application_id:
            raise LineageBroken("the named HTML does not belong to the revision's Application")
        return self.download_artifact(html_artifact_version_id)

    def _artifact_record(self, artifact_version_id: str) -> dict[str, Any]:
        try:
            with self._transactions.read() as tx:
                return self._catalog.artifact_version(tx, artifact_version_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown artifact version: {artifact_version_id}") from exc

    def ready_qualification(
        self,
        application_id: str,
        approved_revision_id: str | None = None,
        pdf_artifact_version_id: str | None = None,
    ) -> ReadyQualification:
        try:
            with self._transactions.read() as tx:
                evidence = self._ready_evidence.load(
                    tx, application_id, approved_revision_id, pdf_artifact_version_id
                )
            return qualify_ready_revision(
                self.revision_payloads,
                evidence,
                application_id,
            )
        except UnknownRecord as exc:
            raise UnknownRecord(f"no approved revision for application: {application_id}") from exc

    def ready_report(self, application_id: str) -> ValidationReport:
        return self.ready_qualification(application_id).validation
