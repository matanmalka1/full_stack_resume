from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...domain.knowledge import Knowledge
from ...domain.models import (
    DraftDocument,
    JobAnalysis,
    Profile,
    ReadyQualification,
    ValidationReport,
)
from ...domain.validation import validate_draft
from ...util import new_id, sha256_file
from ..artifacts import ArtifactDelivery, deliver_artifact
from ..commands import (
    RenderCommand,
    RenderResult,
)
from ..errors import (
    # Re-exported: the v1 CLI and test suite catch WorkflowError from here, and
    # it is bound to the taxonomy's base class, so every refusal below is caught.
    ApplicationError,
    InfrastructureFailure,
    LineageBroken,
    StateConflict,
    UnknownRecord,
    ValidationBlocked,
)
from ..ports import (
    ReadinessRepository,
    RenderTargets,
)
from ..queries import artifact_version_view
from ..ready import qualify_ready_revision
from .base import ServiceBase, bound_analysis


@dataclass(frozen=True)
class PreparedRender:
    command: RenderCommand
    knowledge: Knowledge
    draft: DraftDocument
    profile: Profile
    analysis: JobAnalysis
    source_report: ValidationReport
    manifest_record: dict[str, Any]
    artifact_ids: tuple[str, str, str]
    targets: RenderTargets


@dataclass(frozen=True)
class ExecutedRender:
    prepared: PreparedRender
    report: ValidationReport


class RenderingService(ServiceBase[ReadinessRepository]):
    """Rendering an approved revision and reporting ready state."""

    def render(self, application_id: str) -> RenderResult:
        try:
            revision_id = self.repo.latest_approved_revision(application_id).id
        except UnknownRecord as exc:
            raise UnknownRecord(f"no approved revision for application: {application_id}") from exc
        command = RenderCommand(
            application_id=application_id,
            approved_revision_id=revision_id,
        )
        prepared = self.prepare(command)
        executed = self.execute(prepared)
        return self.activate(executed)

    def prepare(self, command: RenderCommand) -> PreparedRender:
        knowledge = self.load_knowledge()
        facts, profiles, policies = knowledge.facts, knowledge.profiles, knowledge.policies
        try:
            revision = self.repo.approved_revision(command.approved_revision_id)
            manifest_record = self.repo.artifact_version_for_revision(
                command.approved_revision_id, "claim_manifest", "approved"
            )
        except UnknownRecord as exc:
            raise UnknownRecord(
                f"unknown approved revision: {command.approved_revision_id}"
            ) from exc
        if revision.application_id != command.application_id:
            raise LineageBroken("approved revision does not belong to the named Application")
        try:
            manifest_path = self.artifacts.resolve(manifest_record["path"])
        except (OSError, ValueError) as exc:
            raise InfrastructureFailure(f"could not resolve approved revision: {exc}") from exc
        draft = self.stored_draft(manifest_path)
        profile = profiles.get(draft.profile)
        _, analysis = bound_analysis(
            self.repo,
            command.application_id,
            draft,
            profiles,
            facts,
            recorded_analysis_id=self.repo.decision_for_revision(command.approved_revision_id)[
                "job_analysis_id"
            ],
        )
        source_report = validate_draft(
            draft,
            self.artifact_text(self.artifacts.paths_beside(manifest_path).markdown),
            facts,
            profile,
            analysis,
            policies=policies,
            presentations=knowledge.presentations,
        )
        self.repo.record_validation(
            command.application_id, "approved-source-pre-render", source_report
        )
        if not source_report.passed:
            raise ValidationBlocked(
                "render blocked because the approved Markdown no longer matches its validated claims",
                source_report,
            )
        candidate = knowledge.candidate
        artifact_ids = (new_id(), new_id(), new_id())
        recruiter_pdf_filename = self.renderer.filename_for(profile.normalized_role, candidate)
        targets = self.revision_payloads.render_targets(
            command.application_id,
            command.approved_revision_id,
            artifact_ids[0],
            artifact_ids[1],
            artifact_ids[2],
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
        html_path, pdf_path, screenshot_path = targets.html, targets.pdf, targets.screenshot
        try:
            self.renderer.render_html(draft, html_path, candidate)
            geometry = self.renderer.render_pdf(html_path, pdf_path, screenshot_path)
            report = self.renderer.validate_rendered(
                draft,
                prepared.profile,
                html_path,
                pdf_path,
                screenshot_path,
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
        return ExecutedRender(prepared=prepared, report=report)

    def activate(
        self,
        executed: ExecutedRender,
        repository: ReadinessRepository | None = None,
    ) -> RenderResult:
        repo = repository or self.repo
        prepared = executed.prepared
        command = prepared.command
        report = executed.report
        draft = prepared.draft
        facts = prepared.knowledge.facts
        artifact_ids = prepared.artifact_ids
        targets = prepared.targets
        html_path, pdf_path, screenshot_path = targets.html, targets.pdf, targets.screenshot
        lifecycle = "rendered" if report.passed else "rendered-invalid"
        for artifact_version_id, artifact_type, logical_name, path in [
            (artifact_ids[0], "resume_html", "resume", html_path),
            (artifact_ids[1], "resume_pdf", "resume", pdf_path),
            (artifact_ids[2], "visual_evidence", "resume", screenshot_path),
        ]:
            metadata: dict[str, Any] = {"validation_passed": report.passed}
            if artifact_type == "resume_pdf":
                metadata["recruiter_filename"] = targets.recruiter_pdf_filename
            registered_id = repo.register_artifact_version(
                command.application_id,
                artifact_type,
                logical_name,
                self.artifacts.relative(path),
                sha256_file(path),
                lifecycle,
                revision_id=command.approved_revision_id,
                job_snapshot_id=draft.job_snapshot_id,
                track=draft.track.value,
                profile=draft.profile.value,
                emphasis=draft.emphasis.value,
                facts_version=facts.version,
                approved_at=prepared.manifest_record["approved_at"],
                metadata=metadata,
                artifact_version_id=artifact_version_id,
            )
            if registered_id != artifact_version_id:
                raise InfrastructureFailure(
                    "artifact registry did not preserve the reserved output identity"
                )
        repo.record_validation(command.application_id, "post-render", report, artifact_ids[1])
        if report.passed:
            qualification = qualify_ready_revision(
                self.artifacts,
                repo,
                command.application_id,
                command.approved_revision_id,
                artifact_ids[1],
            )
            if not qualification.ready_qualified:
                raise ValidationBlocked(
                    "render succeeded but fresh ready integrity verification failed: "
                    f"{[issue.code for issue in qualification.validation.issues]}"
                )
        return RenderResult(
            application_id=command.application_id,
            pdf_artifact_version_id=artifact_ids[1],
            validation=report,
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
        preview, the screenshot, the approved Markdown, and the archived draft
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
            revision = self.repo.approved_revision(approved_revision_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown approved revision: {approved_revision_id}") from exc
        if record["artifact_type"] != "resume_pdf":
            raise LineageBroken(f"artifact {pdf_artifact_version_id} is not a rendered PDF")
        if record["revision_id"] != revision.id:
            raise LineageBroken("the named PDF does not belong to the named approved revision")
        qualification = qualify_ready_revision(
            self.artifacts,
            self.repo,
            revision.application_id,
            revision.id,
            pdf_artifact_version_id,
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

    def _artifact_record(self, artifact_version_id: str) -> dict[str, Any]:
        try:
            return self.repo.artifact_version(artifact_version_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown artifact version: {artifact_version_id}") from exc

    def revision_ready_qualification(self, approved_revision_id: str) -> ReadyQualification:
        """§20: Ready qualification for one exact revision, by its own ID.

        The Application is read from the revision rather than taken from the
        caller: a revision names exactly one, so a second argument could only
        ever agree or be wrong.
        """
        try:
            revision = self.repo.approved_revision(approved_revision_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown approved revision: {approved_revision_id}") from exc
        return qualify_ready_revision(
            self.artifacts, self.repo, revision.application_id, revision.id
        )

    def ready_qualification(
        self,
        application_id: str,
        approved_revision_id: str | None = None,
        pdf_artifact_version_id: str | None = None,
    ) -> ReadyQualification:
        try:
            self.repo.get_application(application_id)
            return qualify_ready_revision(
                self.artifacts,
                self.repo,
                application_id,
                approved_revision_id,
                pdf_artifact_version_id,
            )
        except UnknownRecord as exc:
            raise UnknownRecord(f"no approved revision for application: {application_id}") from exc

    def ready_report(self, application_id: str) -> ValidationReport:
        return self.ready_qualification(application_id).validation
