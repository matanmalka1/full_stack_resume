from __future__ import annotations

from pathlib import Path
from typing import Any

from .db import Repository
from .drafts import load_draft
from .facts import FactStore
from .models import ValidationIssue, ValidationReport
from .profiles import ProfileStore
from .selection import EmphasisPolicyStore
from .util import sha256_file
from .validation import validate_draft


def verify_ready_integrity(root: Path, repo: Repository, application_id: str) -> ValidationReport:
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
        markdown_version = repo.latest_artifact_version(application_id, "resume_markdown", "approved")
    except KeyError:
        fail("approved_source", "no-approved-markdown", "no approved resume_markdown artifact exists")
        markdown_version = None
    try:
        manifest_version = repo.latest_artifact_version(application_id, "claim_manifest", "approved")
    except KeyError:
        fail("approved_source", "no-approved-manifest", "no approved claim_manifest artifact exists")
        manifest_version = None

    if markdown_version is None or manifest_version is None:
        return ValidationReport(passed=False, groups=groups, issues=issues, evidence=evidence)

    markdown_path = root / markdown_version["path"]
    manifest_path = root / manifest_version["path"]
    markdown_dir = markdown_path.parent
    if manifest_path.parent != markdown_dir:
        fail(
            "approved_source",
            "markdown-manifest-version-mismatch",
            "the latest approved markdown and claim manifest are not the same approved version",
        )

    if not markdown_path.is_file():
        fail("approved_source", "approved-markdown-missing", str(markdown_path))
    elif sha256_file(markdown_path) != markdown_version["content_hash"]:
        fail("approved_source", "approved-markdown-tampered", str(markdown_path))
    if not manifest_path.is_file():
        fail("approved_source", "approved-manifest-missing", str(manifest_path))
    elif sha256_file(manifest_path) != manifest_version["content_hash"]:
        fail("approved_source", "approved-manifest-tampered", str(manifest_path))

    draft = None
    if groups["approved_source"]:
        try:
            draft = load_draft(manifest_path)
        except Exception as exc:  # noqa: BLE001 - any load failure is a hard integrity failure
            fail("approved_source", "manifest-unreadable", str(exc))

    if draft is not None:
        try:
            facts = FactStore.load(root / "base")
            profiles = ProfileStore.load(root, facts)
            policies = EmphasisPolicyStore.load(root)
            profile = profiles.get(draft.profile)
            _, analysis = repo.latest_analysis(application_id)
        except KeyError:
            fail("approved_source", "no-analysis", "no job analysis exists for this application")
        except Exception as exc:  # noqa: BLE001 - knowledge load failure blocks ready
            fail("approved_source", "knowledge-load-failed", str(exc))
        else:
            source_report = validate_draft(
                draft, markdown_path, facts, profile, analysis, policies=policies
            )
            evidence["source_validation"] = source_report.model_dump(mode="json")
            if not source_report.passed:
                fail(
                    "approved_source",
                    "claim-validation-failed",
                    "; ".join(issue.code for issue in source_report.issues) or "content validation failed",
                )

    try:
        pdf_version = repo.latest_artifact_version(application_id, "resume_pdf", "rendered")
    except KeyError:
        fail("rendered_artifacts", "no-rendered-pdf", "no successfully rendered PDF exists")
        pdf_version = None

    if pdf_version is not None:
        pdf_dir = (root / pdf_version["path"]).parent
        if pdf_dir != markdown_dir:
            fail(
                "not_stale",
                "superseded-by-newer-version",
                "the latest approved version is not the version behind the last successful render",
            )
        pdf_path = root / pdf_version["path"]
        if not pdf_path.is_file():
            fail("rendered_artifacts", "pdf-missing", str(pdf_path))
        elif sha256_file(pdf_path) != pdf_version["content_hash"]:
            fail("rendered_artifacts", "pdf-tampered", str(pdf_path))

        for artifact_type, label in (("resume_html", "html"), ("visual_evidence", "visual")):
            try:
                version = repo.latest_artifact_version(application_id, artifact_type, "rendered")
            except KeyError:
                fail("rendered_artifacts", f"no-{label}", f"no successfully rendered {label} artifact exists")
                continue
            path = root / version["path"]
            if path.parent != pdf_dir:
                fail(
                    "rendered_artifacts",
                    f"{label}-version-mismatch",
                    f"rendered {label} artifact is not from the same version as the ready PDF",
                )
            elif not path.is_file():
                fail("rendered_artifacts", f"{label}-missing", str(path))
            elif sha256_file(path) != version["content_hash"]:
                fail("rendered_artifacts", f"{label}-tampered", str(path))

        try:
            post_render = repo.validation_for_artifact(application_id, "post-render", pdf_version["id"])
        except KeyError:
            fail(
                "validation_linkage",
                "no-post-render-validation",
                "no post-render validation references this exact PDF artifact version",
            )
        else:
            evidence["post_render_validation"] = post_render.model_dump(mode="json")
            if not post_render.passed:
                fail("validation_linkage", "post-render-validation-failed", "referenced post-render validation did not pass")

    try:
        decision = repo.decision_for_artifact_version(markdown_version["id"])
    except KeyError:
        fail("not_stale", "no-decision-record", "no decision record exists for the latest approved version")
        decision = None

    if decision is not None:
        latest_snapshot = repo.latest_snapshot(application_id)
        if decision["job_snapshot_id"] != latest_snapshot["id"]:
            fail("not_stale", "new-job-snapshot-since-approval", "a newer job snapshot exists since this version was approved")
        try:
            latest_analysis_id, _ = repo.latest_analysis(application_id)
        except KeyError:
            latest_analysis_id = None
        if decision["job_analysis_id"] != latest_analysis_id:
            fail("not_stale", "new-analysis-since-approval", "a newer job analysis exists since this version was approved")

    problems = repo.integrity_check()
    if problems:
        fail("database_integrity", "db-integrity", "; ".join(problems))

    if pdf_version is not None:
        evidence["pdf_artifact_version_id"] = pdf_version["id"]
        evidence["pdf_path"] = pdf_version["path"]

    return ValidationReport(passed=all(groups.values()), groups=groups, issues=issues, evidence=evidence)
