from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from . import __version__
from .analysis import classify_job
from .db import Repository
from .drafts import build_draft, load_draft, register_linked_claim, write_working_draft
from .facts import FactStore
from .models import ApplicationStatus, JobAnalysis, ValidationReport
from .profiles import ProfileStore
from .providers import OpenAIResponsesProvider
from .rendering import normalized_role_filename, render_html, render_pdf, validate_rendered
from .util import sha256_file, utc_now
from .validation import validate_draft


class WorkflowError(RuntimeError):
    pass


class Engine:
    def __init__(self, repo_root: Path, db_path: Path | None = None):
        self.root = repo_root.resolve()
        self.db_path = db_path or self.root / "data" / "applications.sqlite3"
        self.repo = Repository(self.db_path)

    def knowledge(self) -> tuple[FactStore, ProfileStore]:
        facts = FactStore.load(self.root / "base")
        return facts, ProfileStore.load(self.root, facts)

    def ingest(self, company: str, role: str, job_text: str, url: str | None = None) -> tuple[str, str]:
        return self.repo.create_application(
            company=company,
            target_role=role,
            original_job_text=job_text,
            source_url=url,
        )

    def analyze(
        self,
        application_id: str,
        *,
        track: str | None = None,
        profile: str | None = None,
        emphasis: str | None = None,
        language: str | None = None,
        accept_low_fit: bool = False,
        provider: str = "deterministic",
        model: str = "rules-v1",
    ) -> tuple[str, JobAnalysis]:
        snapshot = self.repo.latest_snapshot(application_id)
        deterministic = classify_job(
            snapshot["original_text"],
            track_override=track,
            profile_override=profile,
            emphasis_override=emphasis,
            language_override=language,
        )
        result = deterministic
        used_provider, used_model = "deterministic", "rules-v1"
        if provider == "openai":
            adapter = OpenAIResponsesProvider(
                model=model,
                prompt_path=self.root / "ai" / "prompts" / "system-v1.md",
            )
            proposal, _ = adapter.run(
                "classify_job",
                {
                    "job_text": snapshot["original_text"],
                    "deterministic_hard_gaps": [gap.model_dump(mode="json") for gap in deterministic.gaps if gap.severity == "hard"],
                    "overrides": deterministic.user_override,
                },
                JobAnalysis,
            )
            hard = {gap.requirement: gap for gap in proposal.gaps}
            for gap in deterministic.gaps:
                if gap.severity == "hard":
                    hard[gap.requirement] = gap
            result = proposal.model_copy(update={
                "gaps": list(hard.values()),
                "fit": deterministic.fit if deterministic.fit.value == "low" else proposal.fit,
                "user_override": deterministic.user_override,
            })
            used_provider, used_model = "openai", model
        elif provider != "deterministic":
            raise WorkflowError(f"unsupported provider: {provider}")

        if accept_low_fit:
            overrides = dict(result.user_override)
            overrides["fit"] = "accepted-low-fit"
            result = result.model_copy(update={"user_override": overrides})
        analysis_id = self.repo.save_analysis(
            application_id,
            snapshot["id"],
            result,
            provider=used_provider,
            model=used_model,
        )
        facts, profiles = self.knowledge()
        selected_profile = profiles.get(result.profile)
        if result.track is not selected_profile.track:
            raise WorkflowError("classified Track and Profile are inconsistent")
        self.repo.set_normalized_role(application_id, selected_profile.normalized_role)
        return analysis_id, result

    def draft(self, application_id: str) -> tuple[Path, Path, ValidationReport]:
        facts, profiles = self.knowledge()
        _, analysis = self.repo.latest_analysis(application_id)
        if analysis.fit.value == "low" and analysis.user_override.get("fit") != "accepted-low-fit":
            raise WorkflowError("low fit blocks CV generation until --accept-low-fit is recorded")
        classification_overridden = any(
            key in analysis.user_override for key in ("track", "profile", "emphasis")
        )
        if analysis.classification_requires_approval and not classification_overridden:
            raise WorkflowError("ambiguous classification requires an explicit Track/Profile override")
        snapshot = self.repo.latest_snapshot(application_id)
        profile = profiles.get(analysis.profile)
        draft = build_draft(
            application_id=application_id,
            job_snapshot_id=snapshot["id"],
            analysis=analysis,
            profile=profile,
            facts=facts,
        )
        markdown, manifest = write_working_draft(self.root, draft)
        report = validate_draft(draft, markdown, facts, profile, analysis)
        self.repo.record_validation(application_id, "pre-render", report)
        self.repo.record_generation_run({
            "application_id": application_id,
            "engine_version": __version__,
            "profile_version": profiles.version,
            "rendering_rules_version": "1.0.0",
            "facts_version": facts.version,
            "ai_provider": "deterministic",
            "ai_model": "rules-v1",
            "task_contract_version": "1.0.0",
            "prompt_version": "system-v1",
            "job_analysis_version": analysis.analysis_version,
            "instruction_overrides": analysis.user_override,
            "status": "completed" if report.passed else "validation-failed",
        })
        return markdown, manifest, report

    def validate_working(self, application_id: str) -> ValidationReport:
        facts, profiles = self.knowledge()
        _, analysis = self.repo.latest_analysis(application_id)
        target = self.root / "artifacts" / "working" / application_id
        draft = load_draft(target / "resume.claims.json")
        report = validate_draft(draft, target / "resume.md", facts, profiles.get(draft.profile), analysis)
        self.repo.record_validation(application_id, "pre-render", report)
        return report

    def link_claim(self, application_id: str, claim_id: str, text: str, fact_ids: list[str]) -> tuple[Path, ValidationReport]:
        facts, profiles = self.knowledge()
        _, analysis = self.repo.latest_analysis(application_id)
        target = self.root / "artifacts" / "working" / application_id
        draft = load_draft(target / "resume.claims.json")
        updated = register_linked_claim(draft, claim_id, text, fact_ids, facts)
        markdown, _ = write_working_draft(self.root, updated)
        report = validate_draft(updated, markdown, facts, profiles.get(updated.profile), analysis)
        self.repo.record_validation(application_id, "manual-claim-linkage", report)
        return markdown, report

    def ready_report(self, application_id: str) -> ValidationReport:
        application = self.repo.get_application(application_id)
        report = self.repo.latest_validation(application_id, "post-render")
        if application["current_status"] != ApplicationStatus.READY.value or not report.passed:
            raise WorkflowError("application is not ready")
        return report

    def approve(self, application_id: str) -> dict[str, Any]:
        report = self.validate_working(application_id)
        if not report.passed:
            raise WorkflowError("approval blocked by pre-render validation")
        facts, profiles = self.knowledge()
        analysis_id, analysis = self.repo.latest_analysis(application_id)
        working = self.root / "artifacts" / "working" / application_id
        draft = load_draft(working / "resume.claims.json")
        existing = [
            row for row in self.repo.artifact_versions(application_id)
            if row["artifact_type"] == "resume_markdown"
        ]
        version = len(existing) + 1
        approved_dir = self.root / "artifacts" / application_id / f"v{version:03d}"
        if approved_dir.exists():
            raise WorkflowError(f"approved version directory already exists: {approved_dir}")
        approved_dir.mkdir(parents=True)
        markdown_path = approved_dir / "resume.md"
        manifest_path = approved_dir / "resume.claims.json"
        shutil.copy2(working / "resume.md", markdown_path)
        shutil.copy2(working / "resume.claims.json", manifest_path)
        now = utc_now()
        relative_markdown = markdown_path.relative_to(self.root).as_posix()
        markdown_version_id = self.repo.register_artifact_version(
            application_id,
            "resume_markdown",
            "resume",
            relative_markdown,
            sha256_file(markdown_path),
            "approved",
            job_snapshot_id=draft.job_snapshot_id,
            track=draft.track.value,
            profile=draft.profile.value,
            emphasis=draft.emphasis.value,
            facts_version=facts.version,
            approved_at=now,
        )
        self.repo.register_artifact_version(
            application_id,
            "claim_manifest",
            "resume-claims",
            manifest_path.relative_to(self.root).as_posix(),
            sha256_file(manifest_path),
            "approved",
            job_snapshot_id=draft.job_snapshot_id,
            track=draft.track.value,
            profile=draft.profile.value,
            emphasis=draft.emphasis.value,
            facts_version=facts.version,
            approved_at=now,
        )
        expected_pdf = approved_dir / normalized_role_filename(profiles.get(draft.profile).normalized_role)
        application = self.repo.get_application(application_id)
        structured = {
            "company": application["company"],
            "target_job": application["target_role"],
            "track": draft.track.value,
            "profile": draft.profile.value,
            "emphasis": draft.emphasis.value,
            "confidence": analysis.confidence,
            "rationale": analysis.rationale,
            "fit": analysis.fit.value,
            "gaps": [gap.model_dump(mode="json") for gap in analysis.gaps],
            "selected_fact_ids": draft.selected_fact_ids,
            "omitted_facts": draft.omitted_facts,
            "derived_statements": [
                claim.model_dump(mode="json") for section in draft.sections
                for claim in section.claims if claim.claim_type in {"composite", "derived"}
            ],
            "accepted_warnings_or_gaps": analysis.user_override,
            "user_overrides": analysis.user_override,
            "fact_store_version": facts.version,
            "job_snapshot_id": draft.job_snapshot_id,
            "job_analysis_id": analysis_id,
            "artifact_paths": {
                "markdown": relative_markdown,
                "html": (approved_dir / "resume.html").relative_to(self.root).as_posix(),
                "pdf": expected_pdf.relative_to(self.root).as_posix(),
            },
        }
        decision_id = self.repo.record_decision(
            application_id,
            markdown_version_id,
            draft.job_snapshot_id,
            analysis_id,
            structured,
            f"Approved {draft.profile.value} / {draft.emphasis.value} CV for {application['company']}.",
        )
        self.repo.record_event(application_id, "draft_approved", {"decision_record_id": decision_id, "version": version})
        return {"version": version, "directory": approved_dir, "decision_record_id": decision_id}

    def render(self, application_id: str) -> tuple[Path, ValidationReport]:
        facts, profiles = self.knowledge()
        manifest_record = self.repo.latest_artifact_version(application_id, "claim_manifest", "approved")
        manifest_path = self.root / manifest_record["path"]
        draft = load_draft(manifest_path)
        profile = profiles.get(draft.profile)
        directory = manifest_path.parent
        _, analysis = self.repo.latest_analysis(application_id)
        source_report = validate_draft(draft, directory / "resume.md", facts, profile, analysis)
        self.repo.record_validation(application_id, "approved-source-pre-render", source_report)
        if not source_report.passed:
            raise WorkflowError("render blocked because the approved Markdown no longer matches its validated claims")
        html_path = directory / "resume.html"
        pdf_path = directory / normalized_role_filename(profile.normalized_role)
        screenshot_path = directory / "visual.png"
        render_html(draft, self.root, html_path)
        geometry = render_pdf(html_path, pdf_path, screenshot_path)
        report = validate_rendered(draft, profile, html_path, pdf_path, screenshot_path, geometry)
        lifecycle = "rendered" if report.passed else "rendered-invalid"
        artifact_ids = []
        for artifact_type, logical_name, path in [
            ("resume_html", "resume", html_path),
            ("resume_pdf", "resume", pdf_path),
            ("visual_evidence", "resume", screenshot_path),
        ]:
            artifact_ids.append(self.repo.register_artifact_version(
                application_id,
                artifact_type,
                logical_name,
                path.relative_to(self.root).as_posix(),
                sha256_file(path),
                lifecycle,
                job_snapshot_id=draft.job_snapshot_id,
                track=draft.track.value,
                profile=draft.profile.value,
                emphasis=draft.emphasis.value,
                facts_version=facts.version,
                approved_at=manifest_record["approved_at"],
                metadata={"validation_passed": report.passed},
            ))
        self.repo.record_validation(application_id, "post-render", report, artifact_ids[1])
        if report.passed:
            self.repo.transition_status(application_id, ApplicationStatus.READY, "all ready validation groups passed")
        return pdf_path, report

    def fast(
        self,
        company: str,
        role: str,
        job_text: str,
        *,
        url: str | None = None,
        track: str | None = None,
        profile: str | None = None,
        emphasis: str | None = None,
        language: str | None = None,
        accept_low_fit: bool = False,
    ) -> dict[str, Any]:
        application_id, _ = self.ingest(company, role, job_text, url)
        self.analyze(
            application_id,
            track=track,
            profile=profile,
            emphasis=emphasis,
            language=language,
            accept_low_fit=accept_low_fit,
        )
        _, _, report = self.draft(application_id)
        if not report.passed:
            raise WorkflowError("fast mode blocked by pre-render validation")
        approval = self.approve(application_id)
        pdf, ready_report = self.render(application_id)
        if not ready_report.passed:
            raise WorkflowError("fast mode blocked by post-render validation")
        return {"application_id": application_id, "approval": approval, "pdf": str(pdf), "ready": True}
