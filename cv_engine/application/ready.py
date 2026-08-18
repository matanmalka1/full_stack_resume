from __future__ import annotations

from typing import Any

from .chain import check_draft_chain, decision_record_analysis_id, material_analysis_key
from .ports import ArtifactStore, KnowledgeStore, ReadinessRepository
from ..domain.models import ValidationIssue, ValidationReport
from ..util import verify_payload
from ..domain.validation import validate_draft


def verify_ready_integrity(
    artifacts: ArtifactStore,
    knowledge: KnowledgeStore,
    repo: ReadinessRepository,
    application_id: str,
) -> ValidationReport:
    """The single domain-level contract for what READY means.

    Re-derives, from disk and DB state right now, that the exact approved source
    and rendered artifacts that once passed the ready pipeline still exist,
    still hash-match their registered immutable versions, are still linked to a
    passing post-render validation, and have not been superseded by a newer
    approved version, job snapshot, or job analysis. A persisted ``passed: true``
    flag on an old validation row is never trusted on its own.
    """
    groups = {
        "approved_source": True,
        "chain": True,
        "rendered_artifacts": True,
        "validation_linkage": True,
        "not_stale": True,
        "database_integrity": True,
    }
    issues: list[ValidationIssue] = []
    evidence: dict[str, Any] = {}

    def fail(group: str, code: str, message: str) -> None:
        groups[group] = False
        issues.append(ValidationIssue(group=group, code=code, message=message))

    try:
        markdown_version = repo.latest_artifact_version(
            application_id, "resume_markdown", "approved"
        )
    except KeyError:
        fail(
            "approved_source", "no-approved-markdown", "no approved resume_markdown artifact exists"
        )
        markdown_version = None
    try:
        manifest_version = repo.latest_artifact_version(
            application_id, "claim_manifest", "approved"
        )
    except KeyError:
        fail(
            "approved_source", "no-approved-manifest", "no approved claim_manifest artifact exists"
        )
        manifest_version = None

    if markdown_version is None or manifest_version is None:
        return ValidationReport.from_findings(groups=groups, issues=issues, evidence=evidence)

    markdown_path = artifacts.resolve(markdown_version["path"])
    manifest_path = artifacts.resolve(manifest_version["path"])
    markdown_dir = markdown_path.parent
    approved_revision_binding = (
        markdown_version.get("revision_id"),
        manifest_version.get("revision_id"),
    )
    if (
        any(approved_revision_binding)
        and approved_revision_binding[0] != approved_revision_binding[1]
    ) or (not any(approved_revision_binding) and manifest_path.parent != markdown_dir):
        fail(
            "approved_source",
            "markdown-manifest-version-mismatch",
            "the latest approved markdown and claim manifest are not the same approved version",
        )

    markdown_verification = verify_payload(markdown_path, markdown_version["content_hash"])
    if markdown_verification == "missing":
        fail("approved_source", "approved-markdown-missing", str(markdown_path))
    elif markdown_verification == "tampered":
        fail("approved_source", "approved-markdown-tampered", str(markdown_path))
    manifest_verification = verify_payload(manifest_path, manifest_version["content_hash"])
    if manifest_verification == "missing":
        fail("approved_source", "approved-manifest-missing", str(manifest_path))
    elif manifest_verification == "tampered":
        fail("approved_source", "approved-manifest-tampered", str(manifest_path))

    draft = None
    if groups["approved_source"]:
        try:
            draft = artifacts.load_draft(manifest_path)
        except Exception as exc:  # noqa: BLE001 - any load failure is a hard integrity failure
            fail("approved_source", "manifest-unreadable", str(exc))

    chain = None
    if draft is not None:
        try:
            loaded = knowledge.load()
            facts, profiles, policies = loaded.facts, loaded.profiles, loaded.policies
            presentations = loaded.presentations
            profile = profiles.get(draft.profile)
        except Exception as exc:  # noqa: BLE001 - knowledge load failure blocks ready
            fail("approved_source", "knowledge-load-failed", str(exc))
        else:
            # The whole chain is re-derived here rather than trusted from the
            # approval that once passed it: ownership, the exact snapshot and
            # analysis, the classification triple, the language, and the fact-store
            # version are all checked against the database as it stands now.
            chain = check_draft_chain(
                repo,
                application_id,
                draft,
                profiles,
                facts,
                recorded_analysis_id=decision_record_analysis_id(repo, application_id),
            )
            evidence["chain"] = {
                "job_snapshot_id": chain.job_snapshot_id,
                "job_analysis_id": chain.job_analysis_id,
            }
            for code, message in chain.problems:
                fail("chain", code, message)
            if chain.valid:
                _, analysis = chain.bound()
                source_report = validate_draft(
                    draft,
                    artifacts.read_document(markdown_path),
                    facts,
                    profile,
                    analysis,
                    policies=policies,
                    presentations=presentations,
                )
                evidence["source_validation"] = source_report.model_dump(mode="json")
                if not source_report.passed:
                    fail(
                        "approved_source",
                        "claim-validation-failed",
                        "; ".join(issue.code for issue in source_report.issues)
                        or "content validation failed",
                    )

    try:
        pdf_version = repo.latest_artifact_version(application_id, "resume_pdf", "rendered")
    except KeyError:
        fail("rendered_artifacts", "no-rendered-pdf", "no successfully rendered PDF exists")
        pdf_version = None

    if pdf_version is not None:
        pdf_dir = artifacts.resolve(pdf_version["path"]).parent
        rendered_revision_binding = (
            markdown_version.get("revision_id"),
            pdf_version.get("revision_id"),
        )
        if (
            any(rendered_revision_binding)
            and rendered_revision_binding[0] != rendered_revision_binding[1]
        ) or (not any(rendered_revision_binding) and pdf_dir != markdown_dir):
            fail(
                "not_stale",
                "superseded-by-newer-version",
                "the latest approved version is not the version behind the last successful render",
            )
        pdf_path = artifacts.resolve(pdf_version["path"])
        pdf_verification = verify_payload(pdf_path, pdf_version["content_hash"])
        if pdf_verification == "missing":
            fail("rendered_artifacts", "pdf-missing", str(pdf_path))
        elif pdf_verification == "tampered":
            fail("rendered_artifacts", "pdf-tampered", str(pdf_path))

        for artifact_type, label in (("resume_html", "html"), ("visual_evidence", "visual")):
            try:
                version = repo.latest_artifact_version(application_id, artifact_type, "rendered")
            except KeyError:
                fail(
                    "rendered_artifacts",
                    f"no-{label}",
                    f"no successfully rendered {label} artifact exists",
                )
                continue
            path = artifacts.resolve(version["path"])
            evidence_revision_binding = (pdf_version.get("revision_id"), version.get("revision_id"))
            if (
                any(evidence_revision_binding)
                and evidence_revision_binding[0] != evidence_revision_binding[1]
            ) or (not any(evidence_revision_binding) and path.parent != pdf_dir):
                fail(
                    "rendered_artifacts",
                    f"{label}-version-mismatch",
                    f"rendered {label} artifact is not from the same version as the ready PDF",
                )
            else:
                verification = verify_payload(path, version["content_hash"])
                if verification == "missing":
                    fail("rendered_artifacts", f"{label}-missing", str(path))
                elif verification == "tampered":
                    fail("rendered_artifacts", f"{label}-tampered", str(path))

        try:
            post_render = repo.validation_for_artifact(
                application_id, "post-render", pdf_version["id"]
            )
        except KeyError:
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
                    "referenced post-render validation did not pass",
                )

    try:
        decision = repo.decision_for_artifact_version(markdown_version["id"])
    except KeyError:
        fail(
            "not_stale",
            "no-decision-record",
            "no decision record exists for the latest approved version",
        )
        decision = None

    if decision is not None:
        # The decision record must describe the same chain position the manifest
        # claims, or one of the two is describing a different document.
        if draft is not None:
            if decision["job_snapshot_id"] != draft.job_snapshot_id:
                fail(
                    "chain",
                    "decision-snapshot-mismatch",
                    "the decision record and the approved manifest name different job snapshots",
                )
            if (
                chain is not None
                and chain.job_analysis_id is not None
                and (decision["job_analysis_id"] != chain.job_analysis_id)
            ):
                fail(
                    "chain",
                    "decision-analysis-mismatch",
                    "the decision record is bound to a different job analysis than the approved draft",
                )
        latest_snapshot = repo.latest_snapshot(application_id)
        if decision["job_snapshot_id"] != latest_snapshot["id"]:
            fail(
                "not_stale",
                "new-job-snapshot-since-approval",
                "a newer job snapshot exists since this version was approved",
            )
        try:
            latest_analysis_id, latest_analysis = repo.latest_analysis(application_id)
            approved_analysis = repo.get_analysis(decision["job_analysis_id"])["analysis"]
        except KeyError:
            fail(
                "not_stale",
                "new-analysis-since-approval",
                "the approved version's job analysis is unavailable",
            )
        else:
            # A re-run that reproduces the same classification, gaps, keywords, and
            # routing does not invalidate a rendered version; a materially different
            # one does.
            if decision["job_analysis_id"] != latest_analysis_id and (
                material_analysis_key(latest_analysis) != material_analysis_key(approved_analysis)
            ):
                fail(
                    "not_stale",
                    "new-analysis-since-approval",
                    "a materially different job analysis exists since this version was approved",
                )

    problems = repo.integrity_check()
    if problems:
        fail("database_integrity", "db-integrity", "; ".join(problems))

    if pdf_version is not None:
        evidence["pdf_artifact_version_id"] = pdf_version["id"]
        evidence["pdf_path"] = pdf_version["path"]

    return ValidationReport.from_findings(groups=groups, issues=issues, evidence=evidence)
