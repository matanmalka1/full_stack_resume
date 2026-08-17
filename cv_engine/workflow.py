from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from . import __version__
from .analysis import classify_job, merge_classification, unresolved_approval_reasons
from .db import Repository
from .drafts import (
    apply_claim_edit,
    build_draft,
    load_draft,
    serialize_markdown,
    synchronize_markdown_claims,
    write_working_draft,
)
from .facts import FactStore, FactStoreError
from .facts import create_fact as persist_new_fact
from .facts import promote_fact as persist_promotion
from .models import (
    ApplicationStatus,
    Fact,
    FactStatus,
    JobAnalysis,
    JobClassificationProposal,
    ValidationReport,
)
from .profiles import ProfileStore, attach_fact_to_section
from .presentations import PresentationStore
from .providers import OpenAIResponsesProvider
from .ready import verify_ready_integrity
from .rendering import normalized_role_filename, render_html, render_pdf, validate_rendered
from .selection import EmphasisPolicyStore
from .util import sha256_file, utc_now
from .validation import validate_draft


class WorkflowError(RuntimeError):
    pass


class Engine:
    def __init__(self, repo_root: Path, db_path: Path | None = None):
        self.root = repo_root.resolve()
        self.db_path = db_path or self.root / "data" / "applications.sqlite3"
        self.repo = Repository(self.db_path)

    def knowledge(self) -> tuple[FactStore, ProfileStore, EmphasisPolicyStore]:
        facts = FactStore.load(self.root / "base")
        return facts, ProfileStore.load(self.root, facts), EmphasisPolicyStore.load(self.root)

    def list_facts(self, status: str | None = None) -> list[dict[str, Any]]:
        facts = FactStore.load(self.root / "base")
        recorded = self.repo.latest_fact_statuses()
        return [
            {**fact.model_dump(mode="json"), "recorded_status": recorded.get(fact.fact_id)}
            for fact in facts.by_status(status)
        ]

    def show_fact(self, fact_id: str) -> dict[str, Any]:
        facts = FactStore.load(self.root / "base")
        return {
            **facts.get(fact_id).model_dump(mode="json"),
            "events": self.repo.fact_events(fact_id),
        }

    def fact_history(self, fact_id: str | None = None) -> list[dict[str, Any]]:
        return self.repo.fact_events(fact_id)

    def _record_fact_event(
        self,
        fact: Fact,
        *,
        event_type: str,
        from_status: str | None,
        reason: str,
        application_id: str | None = None,
        claim_id: str | None = None,
    ) -> dict[str, Any]:
        """Persist the fact change's audit record against the reloaded store.

        The store is reloaded from disk first, so the versions written into the
        trail are the ones a later reader will actually find on disk rather than
        the pre-write ones held in memory.
        """
        facts = FactStore.load(self.root / "base")
        event_id = self.repo.record_fact_event(
            fact_id=fact.fact_id,
            source_file=fact.source_file,
            event_type=event_type,
            from_status=from_status,
            to_status=fact.status.value,
            fact=fact.model_dump(mode="json"),
            facts_version=facts.version,
            lifecycle_version=facts.lifecycle_version,
            reason=reason,
            application_id=application_id,
            claim_id=claim_id,
        )
        return {
            "fact": fact.model_dump(mode="json"),
            "event_id": event_id,
            "facts_version": facts.version,
            "lifecycle_version": facts.lifecycle_version,
        }

    def add_fact(
        self,
        source: str,
        payload: dict[str, Any],
        *,
        canonical: bool = False,
        reason: str = "",
        application_id: str | None = None,
        claim_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new fact in its canonical source file and record the event.

        Without `canonical`, the fact lands as `pending` and cannot reach a CV:
        every rendering path resolves facts with `canonical_only=True`.
        """
        fact = persist_new_fact(self.root / "base", source, payload, canonical=canonical)
        return self._record_fact_event(
            fact,
            event_type="fact_created",
            from_status=None,
            reason=reason or ("explicitly confirmed on creation" if canonical else "new pending fact"),
            application_id=application_id,
            claim_id=claim_id,
        )

    def promote_fact(
        self,
        fact_id: str,
        target: str,
        *,
        explicitly_confirmed: bool,
        reason: str = "",
    ) -> dict[str, Any]:
        before, after = persist_promotion(
            self.root / "base",
            fact_id,
            target,
            explicitly_confirmed=explicitly_confirmed,
        )
        return self._record_fact_event(
            after,
            event_type="fact_promoted",
            from_status=before.status.value,
            reason=reason or f"explicit promotion to {after.status.value}",
        )

    def capture_claim_fact(
        self,
        application_id: str,
        claim_id: str,
        *,
        source: str,
        fact_id: str,
        meaning: str,
        tags: list[str],
        english: str | None = None,
        hebrew: str | None = None,
        provenance: str | None = None,
        effective_dates: str | None = None,
        replaces: str | None = None,
        canonical: bool = False,
        reason: str = "",
    ) -> dict[str, Any]:
        """Turn an unsupported manual claim into a tracked fact.

        This is the product entry point into the lifecycle: a manual edit whose
        wording the fact store cannot support becomes a `pending` claim, and the
        claim's own text becomes the candidate fact rather than being retyped,
        so nothing is strengthened on the way in.
        """
        target = self.root / "artifacts" / "working" / application_id
        draft = load_draft(target / "resume.claims.json")
        claims = [draft.headline, *draft.contacts, *(claim for section in draft.sections for claim in section.claims)]
        try:
            claim = next(item for item in claims if item.claim_id == claim_id)
        except StopIteration as exc:
            raise WorkflowError(f"unknown claim in the working draft: {claim_id}") from exc
        if claim.style == "headline" or claim.claim_type == "headline":
            raise WorkflowError("the document headline is not a factual claim and cannot become a fact")
        renderings: dict[str, str] = {}
        if draft.language == "he":
            renderings["he"] = hebrew or claim.text
            if not english:
                raise WorkflowError(
                    "a fact captured from a Hebrew draft needs its English rendering (--en); "
                    "facts are stored language-neutrally"
                )
            renderings["en"] = english
        else:
            renderings["en"] = english or claim.text
            if hebrew:
                renderings["he"] = hebrew
        return self.add_fact(
            source,
            {
                "fact_id": fact_id,
                "meaning": meaning,
                "renderings": renderings,
                "tags": tags,
                "provenance": provenance or (
                    f"captured from application {application_id} claim {claim_id}; "
                    "candidate wording, not yet verified"
                ),
                "effective_dates": effective_dates,
                "replaces": replaces,
                "resume_style": claim.style,
            },
            canonical=canonical,
            reason=reason or f"captured from claim {claim_id}",
            application_id=application_id,
            claim_id=claim_id,
        )

    def attach_fact(self, fact_id: str, profile: str, section: str, *, pin: bool = False) -> dict[str, Any]:
        """Offer a canonical fact to one Profile section's candidate pool."""
        facts, profiles, _ = self.knowledge()
        try:
            fact = facts.get(fact_id, canonical_only=True)
        except FactStoreError as exc:
            raise WorkflowError(
                f"only canonical facts may enter a Profile pool: {exc}"
            ) from exc
        path = profiles.path(profile)
        updated = attach_fact_to_section(path, fact_id, section, pin=pin)
        # Reload so a Profile that no longer validates against the fact store
        # fails here rather than at the next draft.
        reloaded = ProfileStore.load(self.root, FactStore.load(self.root / "base"))
        record = self._record_fact_event(
            fact,
            event_type="fact_attached_to_profile",
            from_status=fact.status.value,
            reason=f"attached to {updated.profile.value} / {section}" + (" (pinned)" if pin else ""),
        )
        return {
            **record,
            "profile": updated.profile.value,
            "section": section,
            "pinned": pin,
            "profile_path": path.relative_to(self.root).as_posix(),
            "profile_store_version": reloaded.version,
        }

    def reconcile_facts(self) -> dict[str, Any]:
        """Check the persisted lifecycle against its audit trail.

        Three disagreements matter: a trail entry for a fact that no longer
        exists, a live status that the trail never recorded, and a live status
        that contradicts the last recorded one. Each means a status was changed
        outside the lifecycle, which is exactly what the trail exists to catch.
        """
        facts = FactStore.load(self.root / "base")
        recorded = self.repo.latest_fact_statuses()
        problems: list[str] = []
        for fact_id, status in recorded.items():
            if fact_id not in facts.facts:
                problems.append(f"fact event references a fact that no longer exists: {fact_id}")
            elif facts.facts[fact_id].status.value != status:
                problems.append(
                    f"fact {fact_id} is {facts.facts[fact_id].status.value} on disk but the "
                    f"lifecycle trail last recorded {status}"
                )
        untracked = [
            fact.fact_id for fact in facts.by_status()
            if fact.status is not FactStatus.CANONICAL and fact.fact_id not in recorded
        ]
        problems.extend(
            f"non-canonical fact has no lifecycle event: {fact_id}" for fact_id in untracked
        )
        counts = {status.value: len(facts.by_status(status)) for status in FactStatus}
        return {
            "passed": not problems,
            "fact_counts": counts,
            "tracked_facts": len(recorded),
            "facts_version": facts.version,
            "lifecycle_version": facts.lifecycle_version,
            "problems": problems,
        }

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
        _, profiles, _ = self.knowledge()
        if provider == "openai":
            adapter = OpenAIResponsesProvider(
                model=model,
                prompt_path=self.root / "ai" / "prompts" / "system-v1.md",
            )
            # The provider sees the full deterministic picture as context, but it
            # answers on the narrower proposal contract; deterministic policy decides
            # what survives.
            proposal, _ = adapter.run(
                "classify_job",
                {
                    "job_text": snapshot["original_text"],
                    "deterministic_classification": {
                        "track": deterministic.track.value,
                        "profile": deterministic.profile.value,
                        "emphasis": deterministic.emphasis.value,
                        "confidence": deterministic.confidence,
                        "language": deterministic.language,
                    },
                    "deterministic_gaps": [gap.model_dump(mode="json") for gap in deterministic.gaps],
                    "overrides": deterministic.user_override,
                },
                JobClassificationProposal,
            )
            result = merge_classification(deterministic, proposal, profiles)
            used_provider, used_model = "openai", model
        elif provider != "deterministic":
            raise WorkflowError(f"unsupported provider: {provider}")

        if accept_low_fit:
            # Rebuilt through validation rather than model_copy(update=...), which
            # would skip the model validators that guard this state.
            overrides = {**result.user_override, "fit": "accepted-low-fit"}
            result = JobAnalysis.model_validate({**result.model_dump(mode="json"), "user_override": overrides})
        analysis_id = self.repo.save_analysis(
            application_id,
            snapshot["id"],
            result,
            provider=used_provider,
            model=used_model,
        )
        selected_profile = profiles.get(result.profile)
        if result.track is not selected_profile.track:
            raise WorkflowError("classified Track and Profile are inconsistent")
        self.repo.set_normalized_role(application_id, selected_profile.normalized_role)
        return analysis_id, result

    def draft(self, application_id: str) -> tuple[Path, Path, ValidationReport]:
        facts, profiles, policies = self.knowledge()
        _, analysis = self.repo.latest_analysis(application_id)
        if analysis.fit.value == "low" and analysis.user_override.get("fit") != "accepted-low-fit":
            raise WorkflowError("low fit blocks CV generation until --accept-low-fit is recorded")
        unresolved = unresolved_approval_reasons(analysis)
        if unresolved:
            raise WorkflowError(
                "ambiguous classification requires an explicit Track/Profile override: "
                f"{unresolved}"
            )
        snapshot = self.repo.latest_snapshot(application_id)
        profile = profiles.get(analysis.profile)
        draft = build_draft(
            application_id=application_id,
            job_snapshot_id=snapshot["id"],
            analysis=analysis,
            profile=profile,
            facts=facts,
            policies=policies,
        )
        presentation_rules = PresentationStore.for_facts(facts)
        markdown, manifest = write_working_draft(self.root, draft)
        report = validate_draft(draft, markdown, facts, profile, analysis, policies=policies)
        self.repo.record_validation(application_id, "pre-render", report)
        self.repo.record_generation_run({
            "application_id": application_id,
            "engine_version": __version__,
            "profile_version": profiles.version,
            "rendering_rules_version": (
                f"1.0.0+presentations.{presentation_rules.version[:12]}"
                if presentation_rules is not None else "1.0.0"
            ),
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
        facts, profiles, policies = self.knowledge()
        _, analysis = self.repo.latest_analysis(application_id)
        target = self.root / "artifacts" / "working" / application_id
        draft = load_draft(target / "resume.claims.json")
        markdown_path = target / "resume.md"
        actual = markdown_path.read_text(encoding="utf-8") if markdown_path.is_file() else ""
        if actual != serialize_markdown(draft):
            try:
                draft = synchronize_markdown_claims(draft, markdown_path, facts)
            except ValueError:
                pass
            else:
                markdown_path, _ = write_working_draft(self.root, draft)
        report = validate_draft(draft, markdown_path, facts, profiles.get(draft.profile), analysis, policies=policies)
        self.repo.record_validation(application_id, "pre-render", report)
        return report

    def edit_claim(
        self,
        application_id: str,
        claim_id: str,
        fact_ids: list[str],
        *,
        text: str | None = None,
        template_id: str | None = None,
        template_version: str | None = None,
    ) -> tuple[Path, ValidationReport]:
        facts, profiles, policies = self.knowledge()
        _, analysis = self.repo.latest_analysis(application_id)
        target = self.root / "artifacts" / "working" / application_id
        draft = load_draft(target / "resume.claims.json")
        updated = apply_claim_edit(
            draft,
            claim_id,
            fact_ids,
            facts,
            text=text,
            template_id=template_id,
            template_version=template_version,
        )
        markdown, _ = write_working_draft(self.root, updated)
        report = validate_draft(updated, markdown, facts, profiles.get(updated.profile), analysis, policies=policies)
        self.repo.record_validation(application_id, "manual-claim-edit", report)
        return markdown, report

    def link_claim(self, application_id: str, claim_id: str, text: str, fact_ids: list[str]) -> tuple[Path, ValidationReport]:
        return self.edit_claim(application_id, claim_id, fact_ids, text=text)

    def sync_working_claims(self, application_id: str) -> tuple[Path, ValidationReport]:
        facts, profiles, policies = self.knowledge()
        _, analysis = self.repo.latest_analysis(application_id)
        target = self.root / "artifacts" / "working" / application_id
        draft = load_draft(target / "resume.claims.json")
        updated = synchronize_markdown_claims(draft, target / "resume.md", facts)
        markdown, _ = write_working_draft(self.root, updated)
        report = validate_draft(updated, markdown, facts, profiles.get(updated.profile), analysis, policies=policies)
        self.repo.record_validation(application_id, "manual-markdown-sync", report)
        return markdown, report

    def ready_report(self, application_id: str) -> ValidationReport:
        application = self.repo.get_application(application_id)
        if application["current_status"] != ApplicationStatus.READY.value:
            raise WorkflowError("application is not ready")
        return verify_ready_integrity(self.root, self.repo, application_id)

    def approve(self, application_id: str) -> dict[str, Any]:
        report = self.validate_working(application_id)
        if not report.passed:
            raise WorkflowError("approval blocked by pre-render validation")
        facts, profiles, policies = self.knowledge()
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
        if application["current_status"] == ApplicationStatus.READY.value:
            self.repo.transition_status(
                application_id,
                ApplicationStatus.PREPARING,
                "new approved version requires fresh rendering and ready validation",
            )
        return {"version": version, "directory": approved_dir, "decision_record_id": decision_id}

    def render(self, application_id: str) -> tuple[Path, ValidationReport]:
        facts, profiles, policies = self.knowledge()
        manifest_record = self.repo.latest_artifact_version(application_id, "claim_manifest", "approved")
        manifest_path = self.root / manifest_record["path"]
        draft = load_draft(manifest_path)
        profile = profiles.get(draft.profile)
        directory = manifest_path.parent
        _, analysis = self.repo.latest_analysis(application_id)
        source_report = validate_draft(draft, directory / "resume.md", facts, profile, analysis, policies=policies)
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
            integrity = verify_ready_integrity(self.root, self.repo, application_id)
            if not integrity.passed:
                raise WorkflowError(
                    "render succeeded but fresh ready integrity verification failed: "
                    f"{[issue.code for issue in integrity.issues]}"
                )
            self.repo._set_ready(application_id, artifact_ids[1], "all ready validation groups passed")
        return pdf_path, report

    def submit(self, application_id: str, reason: str = "submitted to employer") -> dict[str, Any]:
        application = self.repo.get_application(application_id)
        if application["current_status"] != ApplicationStatus.READY.value:
            raise WorkflowError("applied requires a currently valid ready application")
        integrity = verify_ready_integrity(self.root, self.repo, application_id)
        if not integrity.passed:
            raise WorkflowError(
                "applied blocked by stale or tampered ready state: "
                f"{[issue.code for issue in integrity.issues]}"
            )
        pdf_artifact_version_id = integrity.evidence["pdf_artifact_version_id"]
        self.repo._record_submission(application_id, pdf_artifact_version_id, reason)
        return {
            "application_id": application_id,
            "pdf_artifact_version_id": pdf_artifact_version_id,
            **self.repo.get_application(application_id),
        }

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
