from __future__ import annotations

from typing import Any

from ..domain.draft_markdown import parse_draft
from ..domain.models import ReadyQualification, ValidationIssue, ValidationReport
from .errors import UnknownRecord
from .ports import ReadinessRepository, SnapshotPayloadStore


def qualify_ready_revision(
    payloads: SnapshotPayloadStore,
    repo: ReadinessRepository,
    application_id: str,
    approved_revision_id: str | None = None,
    pdf_artifact_version_id: str | None = None,
) -> ReadyQualification:
    """Re-derive Ready qualification from one revision's stored immutable evidence.

    Qualification belongs to the revision, not to the application's active context or
    recruitment status. The optional IDs are convenience inputs for callers that
    name only the application; once resolved, every check is exact and revision-bound.
    """
    revision = (
        repo.approved_revision(approved_revision_id)
        if approved_revision_id is not None
        else repo.latest_approved_revision(application_id)
    )
    groups = {
        "approved_source": True,
        "chain": True,
        "rendered_artifacts": True,
        "validation_linkage": True,
        "revision_binding": True,
        "database_integrity": True,
    }
    issues: list[ValidationIssue] = []
    evidence: dict[str, Any] = {"approved_revision_id": revision.id}

    def fail(group: str, code: str, message: str) -> None:
        groups[group] = False
        issues.append(ValidationIssue(group=group, code=code, message=message))

    if revision.application_id != application_id:
        fail(
            "revision_binding",
            "revision-application-mismatch",
            f"approved revision {revision.id} does not belong to application {application_id}",
        )

    source_versions: dict[str, dict[str, Any]] = {}
    for artifact_type, label in (
        ("claim_manifest", "manifest"),
        ("resume_markdown", "markdown"),
    ):
        try:
            version = repo.artifact_version_for_revision(revision.id, artifact_type, "approved")
        except UnknownRecord:
            fail(
                "approved_source",
                f"no-approved-{label}",
                f"no approved {artifact_type} artifact exists for revision {revision.id}",
            )
            continue
        source_versions[artifact_type] = version
        if version["application_id"] != application_id:
            fail(
                "revision_binding",
                f"{label}-application-mismatch",
                f"the approved {label} belongs to another application",
            )

    manifest_version = source_versions.get("claim_manifest")
    markdown_version = source_versions.get("resume_markdown")
    expected_sources = (
        (
            manifest_version,
            revision.resume_json_reference,
            revision.resume_json_hash,
            "manifest",
        ),
        (
            markdown_version,
            revision.resume_markdown_reference,
            revision.resume_markdown_hash,
            "markdown",
        ),
    )
    for version, expected_reference, expected_hash, label in expected_sources:
        if version is None:
            continue
        if version["path"] != expected_reference or version["content_hash"] != expected_hash:
            fail(
                "revision_binding",
                f"{label}-revision-mismatch",
                f"the approved {label} row does not match the approved revision payload",
            )
        verification = payloads.verify_payload(version["path"], expected_hash)
        if verification == "unresolvable":
            fail(
                "approved_source",
                f"approved-{label}-unresolvable",
                version["path"],
            )
            continue
        if verification != "ok":
            fail(
                "approved_source",
                f"approved-{label}-{verification}",
                version["path"],
            )

    draft = None
    if manifest_version is not None and groups["approved_source"]:
        try:
            draft = parse_draft(payloads.read_payload_text(manifest_version["path"]))
        except Exception as exc:  # noqa: BLE001 - unreadable immutable input blocks Ready
            fail("approved_source", "manifest-unreadable", str(exc))

    if draft is not None:
        draft_bindings = {
            "application_id": (draft.application_id, revision.application_id),
            "job_snapshot_id": (draft.job_snapshot_id, revision.job_snapshot_id),
            "job_analysis_id": (draft.job_analysis_id, revision.job_analysis_id),
            "content_hash": (draft.content_hash, revision.draft_content_hash),
            "fact_store_version": (draft.fact_store_version, revision.facts_version),
        }
        for field, (actual, expected) in draft_bindings.items():
            if actual != expected:
                fail(
                    "chain",
                    f"draft-{field.replace('_', '-')}-mismatch",
                    f"approved draft {field} does not match its revision",
                )

    try:
        analysis_record = repo.get_analysis(revision.job_analysis_id)
    except UnknownRecord:
        fail("chain", "unknown-job-analysis", "the revision's job analysis is unavailable")
    else:
        if analysis_record["application_id"] != revision.application_id:
            fail("chain", "analysis-application-mismatch", "job analysis ownership differs")
        if analysis_record["job_snapshot_id"] != revision.job_snapshot_id:
            fail("chain", "analysis-snapshot-mismatch", "job analysis snapshot differs")

    try:
        plan = repo.selection_plan(revision.selection_plan_id)
    except UnknownRecord:
        fail("chain", "unknown-selection-plan", "the revision's selection plan is unavailable")
    else:
        if plan.application_id != revision.application_id:
            fail("chain", "plan-application-mismatch", "selection plan ownership differs")
        if plan.job_analysis_id != revision.job_analysis_id:
            fail("chain", "plan-analysis-mismatch", "selection plan analysis differs")
        plan_bindings = {
            "candidate_context_version": revision.candidate_context_version,
            "candidate_context_hash": revision.candidate_context_hash,
            "profile_version": revision.profile_version,
            "selection_policy_version": revision.selection_policy_version,
            "track_emphasis_dependencies": revision.track_emphasis_dependencies,
        }
        for field, expected in plan_bindings.items():
            if getattr(plan, field) != expected:
                fail(
                    "chain",
                    f"plan-{field.replace('_', '-')}-mismatch",
                    f"selection plan {field} differs from the revision",
                )

    if markdown_version is not None:
        try:
            decision = repo.decision_for_artifact_version(markdown_version["id"])
        except UnknownRecord:
            fail(
                "revision_binding",
                "no-decision-record",
                "no decision record exists for the revision's approved Markdown",
            )
        else:
            for field, expected in (
                ("application_id", revision.application_id),
                ("job_snapshot_id", revision.job_snapshot_id),
                ("job_analysis_id", revision.job_analysis_id),
            ):
                if decision[field] != expected:
                    fail(
                        "chain",
                        f"decision-{field.replace('_', '-')}-mismatch",
                        f"the decision record's {field} differs from the revision",
                    )

    try:
        approval_validation = repo.validation_report(revision.validation_run_id)
        lineage = repo.validation_lineage(revision.validation_run_id)
    except UnknownRecord:
        fail(
            "validation_linkage",
            "no-approval-validation",
            "the revision's exact approval validation is unavailable",
        )
    else:
        evidence["approval_validation"] = approval_validation.model_dump(mode="json")
        if not approval_validation.passed:
            fail(
                "validation_linkage",
                "approval-validation-failed",
                "the revision's exact approval validation did not pass",
            )
        lineage_bindings = {
            "working_draft_id": revision.working_draft_id,
            "edit_version": revision.draft_edit_version,
            "content_hash": revision.draft_content_hash,
            "job_snapshot_id": revision.job_snapshot_id,
            "job_analysis_id": revision.job_analysis_id,
            "selection_plan_id": revision.selection_plan_id,
            "knowledge_context_hash": revision.knowledge_context_hash,
            "validator_versions": revision.validator_versions,
        }
        for field, expected in lineage_bindings.items():
            if getattr(lineage, field) != expected:
                fail(
                    "validation_linkage",
                    f"approval-validation-{field.replace('_', '-')}-mismatch",
                    f"the approval validation's {field} differs from the revision",
                )

    pdf_version: dict[str, Any] | None = None
    try:
        pdf_version = (
            repo.artifact_version(pdf_artifact_version_id)
            if pdf_artifact_version_id is not None
            else repo.artifact_version_for_revision(revision.id, "resume_pdf", "rendered")
        )
    except UnknownRecord:
        fail(
            "rendered_artifacts",
            "no-rendered-pdf",
            "no rendered PDF exists for this approved revision",
        )

    rendered_versions: list[tuple[dict[str, Any], str]] = []
    if pdf_version is not None:
        rendered_versions.append((pdf_version, "pdf"))
        expected_pdf = {
            "application_id": application_id,
            "artifact_type": "resume_pdf",
            "lifecycle_status": "rendered",
            "revision_id": revision.id,
        }
        for field, expected in expected_pdf.items():
            if pdf_version[field] != expected:
                fail(
                    "revision_binding",
                    f"pdf-{field.replace('_', '-')}-mismatch",
                    f"the selected PDF's {field} does not match the approved revision",
                )

    html_version: dict[str, Any] | None = None
    for artifact_type, label in (("resume_html", "html"), ("visual_evidence", "visual")):
        try:
            version = repo.artifact_version_for_revision(revision.id, artifact_type, "rendered")
        except UnknownRecord:
            fail(
                "rendered_artifacts",
                f"no-{label}",
                f"no rendered {label} artifact exists for this approved revision",
            )
            continue
        rendered_versions.append((version, label))
        if artifact_type == "resume_html":
            html_version = version
        if version["application_id"] != application_id:
            fail(
                "revision_binding",
                f"{label}-application-mismatch",
                f"the rendered {label} belongs to another application",
            )

    for version, label in rendered_versions:
        verification = payloads.verify_payload(version["path"], version["content_hash"])
        if verification == "unresolvable":
            fail("rendered_artifacts", f"{label}-unresolvable", version["path"])
            continue
        if verification != "ok":
            fail("rendered_artifacts", f"{label}-{verification}", version["path"])

    if pdf_version is not None and groups["revision_binding"]:
        try:
            post_render = repo.validation_for_artifact(
                application_id, "post-render", pdf_version["id"]
            )
        except UnknownRecord:
            fail(
                "validation_linkage",
                "no-post-render-validation",
                "no post-render validation references this exact PDF artifact version",
            )
        else:
            evidence["post_render_validation"] = post_render.model_dump(mode="json")
            if not post_render.passed:
                fail(
                    "validation_linkage",
                    "post-render-validation-failed",
                    "the exact PDF's post-render validation did not pass",
                )

    problems = repo.integrity_check()
    if problems:
        fail("database_integrity", "db-integrity", "; ".join(problems))

    if pdf_version is not None:
        evidence["pdf_artifact_version_id"] = pdf_version["id"]
        evidence["pdf_path"] = pdf_version["path"]

    report = ValidationReport.from_findings(groups=groups, issues=issues, evidence=evidence)
    return ReadyQualification(
        application_id=application_id,
        approved_revision_id=revision.id,
        pdf_artifact_version_id=(pdf_version or {}).get("id"),
        html_artifact_version_id=(html_version or {}).get("id"),
        ready_qualified=report.passed,
        validation=report,
    )
