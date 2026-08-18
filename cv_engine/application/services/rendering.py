from __future__ import annotations

import uuid

from ...domain.models import (
    ReadyQualification,
    ValidationReport,
)
from ...domain.validation import validate_draft
from ...util import sha256_file
from ..chain import decision_record_analysis_id
from ..commands import (
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
)
from ..ready import qualify_ready_revision
from .base import ServiceBase


class RenderingService(ServiceBase[ReadinessRepository]):
    """Rendering an approved revision and reporting ready state."""

    def render(self, application_id: str) -> RenderResult:
        knowledge = self.load_knowledge()
        facts, profiles, policies = knowledge.facts, knowledge.profiles, knowledge.policies
        try:
            manifest_record = self.repo.latest_artifact_version(
                application_id, "claim_manifest", "approved"
            )
        except KeyError as exc:
            raise UnknownRecord(f"no approved revision for application: {application_id}") from exc
        try:
            manifest_path = self.artifacts.resolve(manifest_record["path"])
        except (OSError, ValueError) as exc:
            raise InfrastructureFailure(f"could not resolve approved revision: {exc}") from exc
        draft = self.stored_draft(manifest_path)
        revision_id = manifest_record.get("revision_id")
        profile = profiles.get(draft.profile)
        _, analysis = self._bound_analysis(
            application_id,
            draft,
            profiles,
            facts,
            recorded_analysis_id=decision_record_analysis_id(self.repo, application_id),
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
        self.repo.record_validation(application_id, "approved-source-pre-render", source_report)
        if not source_report.passed:
            raise ValidationBlocked(
                "render blocked because the approved Markdown no longer matches its validated claims",
                source_report,
            )
        candidate = knowledge.candidate
        artifact_ids = [str(uuid.uuid4()) for _ in range(3)]
        recruiter_pdf_filename = self.renderer.filename_for(profile.normalized_role, candidate)
        if revision_id is None:
            raise LineageBroken("rendering requires an approved revision-bound claim manifest")
        targets = self.revision_payloads.render_targets(
            application_id,
            revision_id,
            artifact_ids[0],
            artifact_ids[1],
            artifact_ids[2],
            recruiter_pdf_filename,
        )
        html_path, pdf_path, screenshot_path = targets.html, targets.pdf, targets.screenshot
        try:
            self.renderer.render_html(draft, html_path, candidate)
            geometry = self.renderer.render_pdf(html_path, pdf_path, screenshot_path)
            report = self.renderer.validate_rendered(
                draft,
                profile,
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
        lifecycle = "rendered" if report.passed else "rendered-invalid"
        for artifact_version_id, artifact_type, logical_name, path in [
            (artifact_ids[0], "resume_html", "resume", html_path),
            (artifact_ids[1], "resume_pdf", "resume", pdf_path),
            (artifact_ids[2], "visual_evidence", "resume", screenshot_path),
        ]:
            metadata = {"validation_passed": report.passed}
            if artifact_type == "resume_pdf":
                metadata["recruiter_filename"] = targets.recruiter_pdf_filename
            registered_id = self.repo.register_artifact_version(
                application_id,
                artifact_type,
                logical_name,
                self.artifacts.relative(path),
                sha256_file(path),
                lifecycle,
                revision_id=revision_id,
                job_snapshot_id=draft.job_snapshot_id,
                track=draft.track.value,
                profile=draft.profile.value,
                emphasis=draft.emphasis.value,
                facts_version=facts.version,
                approved_at=manifest_record["approved_at"],
                metadata=metadata,
                artifact_version_id=artifact_version_id,
            )
            if registered_id != artifact_version_id:
                raise InfrastructureFailure(
                    "artifact registry did not preserve the reserved output identity"
                )
        self.repo.record_validation(application_id, "post-render", report, artifact_ids[1])
        if report.passed:
            qualification = qualify_ready_revision(
                self.artifacts,
                self.repo,
                application_id,
                revision_id,
                artifact_ids[1],
            )
            if not qualification.ready_qualified:
                raise ValidationBlocked(
                    "render succeeded but fresh ready integrity verification failed: "
                    f"{[issue.code for issue in qualification.validation.issues]}"
                )
        return RenderResult(
            application_id=application_id,
            pdf_artifact_version_id=artifact_ids[1],
            validation=report,
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
        except KeyError as exc:
            raise UnknownRecord(f"no approved revision for application: {application_id}") from exc

    def ready_report(self, application_id: str) -> ValidationReport:
        return self.ready_qualification(application_id).validation
