from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import __version__
from ..domain.analysis import classify_job, merge_classification, unresolved_approval_reasons
from ..domain.drafts import (
    apply_claim_edit,
    build_draft,
    serialize_markdown,
    synchronize_markdown_claims,
)
from ..domain.facts import FactStore, FactStoreError
from ..domain.knowledge import Knowledge
from ..domain.models import (
    ApplicationStatus,
    CandidateContext,
    DraftDocument,
    Fact,
    FactStatus,
    JobAnalysis,
    ValidationReport,
)
from ..domain.profiles import ProfileStore
from ..domain.selection import EmphasisPolicyStore
from ..domain.validation import validate_draft
from ..util import sha256_file, utc_now
from .chain import ChainError, check_draft_chain, decision_record_analysis_id
from .commands import (
    AnalysisResult,
    ApprovalResult,
    DraftResult,
    EditResult,
    IngestedApplication,
    RenderResult,
    SubmissionResult,
)
from .errors import (
    # Re-exported: the v1 CLI and test suite catch WorkflowError from here, and
    # it is bound to the taxonomy's base class, so every refusal below is caught.
    DependencyUnavailable,
    KnowledgeRejected,
    LineageBroken,
    StateConflict,
    UnknownRecord,
    ValidationBlocked,
    WorkflowError,
)
from .ports import (
    ApplicationRepository,
    ArtifactStore,
    ClassificationProvider,
    KnowledgeStore,
    Renderer,
)
from .ready import verify_ready_integrity


class ServiceBase:
    """Shared dependencies for the application services.

    Every service receives its collaborators explicitly and re-reads knowledge
    per command, so nothing here holds a cache that could disagree with the
    files a later command will read.
    """

    def __init__(
        self,
        *,
        repository: ApplicationRepository,
        knowledge: KnowledgeStore,
        artifacts: ArtifactStore,
        renderer: Renderer | None = None,
        provider: ClassificationProvider | None = None,
    ):
        self.repo = repository
        self.artifacts = artifacts
        self._knowledge = knowledge
        self._renderer = renderer
        self._provider = provider

    def load_knowledge(self) -> Knowledge:
        return self._knowledge.load()

    def knowledge(self) -> tuple[FactStore, ProfileStore, EmphasisPolicyStore]:
        loaded = self._knowledge.load()
        return loaded.facts, loaded.profiles, loaded.policies

    def candidate(self, facts: FactStore | None = None) -> CandidateContext:
        return self._knowledge.load().candidate

    def _bound_analysis(
        self,
        application_id: str,
        draft: DraftDocument,
        profiles: ProfileStore,
        facts: FactStore,
        *,
        recorded_analysis_id: str | None = None,
    ) -> tuple[str, JobAnalysis]:
        """The analysis this exact draft was built from, or a refusal.

        Called before any write on every path that consumes a draft, so a draft
        whose chain no longer holds is rejected while the working area, the
        artifact directory, and SQLite are all still untouched.
        """
        chain = check_draft_chain(
            self.repo,
            application_id,
            draft,
            profiles,
            facts,
            recorded_analysis_id=recorded_analysis_id,
        )
        try:
            return chain.bound()
        except ChainError as exc:
            raise LineageBroken(f"draft chain rejected: {exc}") from exc

    @property
    def renderer(self) -> Renderer:
        if self._renderer is None:
            raise DependencyUnavailable("this command needs a renderer and none was configured")
        return self._renderer


class KnowledgeService(ServiceBase):
    """The fact lifecycle and the knowledge version surface."""

    def knowledge_versions(self) -> dict[str, str]:
        """One hash surface per knowledge dependency an artifact can depend on."""
        return self.load_knowledge().versions()

    def list_facts(self, status: str | None = None) -> list[dict[str, Any]]:
        facts = self._knowledge.facts()
        recorded = self.repo.latest_fact_statuses()
        return [
            {**fact.model_dump(mode="json"), "recorded_status": recorded.get(fact.fact_id)}
            for fact in facts.by_status(status)
        ]

    def show_fact(self, fact_id: str) -> dict[str, Any]:
        facts = self._knowledge.facts()
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
        facts = self._knowledge.facts()
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
        fact = self._knowledge.create_fact(source, payload, canonical=canonical)
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
        before, after = self._knowledge.promote_fact(
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
        draft = self.artifacts.load_working_draft(application_id)
        claims = [draft.headline, *draft.contacts, *(claim for section in draft.sections for claim in section.claims)]
        try:
            claim = next(item for item in claims if item.claim_id == claim_id)
        except StopIteration as exc:
            raise UnknownRecord(f"unknown claim in the working draft: {claim_id}") from exc
        if claim.style == "headline" or claim.claim_type == "headline":
            raise KnowledgeRejected("the document headline is not a factual claim and cannot become a fact")
        renderings: dict[str, str] = {}
        if draft.language == "he":
            renderings["he"] = hebrew or claim.text
            if not english:
                raise KnowledgeRejected(
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
            raise KnowledgeRejected(
                f"only canonical facts may enter a Profile pool: {exc}"
            ) from exc
        updated, source = self._knowledge.attach_fact(profile, fact_id, section, pin=pin)
        # Reload so a Profile that no longer validates against the fact store
        # fails here rather than at the next draft.
        reloaded = self.load_knowledge().profiles
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
            "profile_path": self.artifacts.relative(Path(source)),
            "profile_store_version": reloaded.version,
        }

    def reconcile_facts(self) -> dict[str, Any]:
        """Check the persisted lifecycle against its audit trail.

        Three disagreements matter: a trail entry for a fact that no longer
        exists, a live status that the trail never recorded, and a live status
        that contradicts the last recorded one. Each means a status was changed
        outside the lifecycle, which is exactly what the trail exists to catch.
        """
        facts = self._knowledge.facts()
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


class ApplicationService(ServiceBase):
    """Creating an application and its immutable job snapshot."""

    def ingest(self, company: str, role: str, job_text: str, url: str | None = None) -> IngestedApplication:
        application_id, snapshot_id = self.repo.create_application(
            company=company,
            target_role=role,
            original_job_text=job_text,
            source_url=url,
        )
        return IngestedApplication(application_id, snapshot_id)


class AnalysisService(ServiceBase):
    """Classification, fit, and the analysis record."""

    def analyze(
        self,
        application_id: str,
        job_snapshot_id: str,
        *,
        track: str | None = None,
        profile: str | None = None,
        emphasis: str | None = None,
        language: str | None = None,
        accept_low_fit: bool = False,
        provider: str = "deterministic",
        model: str = "rules-v1",
    ) -> AnalysisResult:
        """Classify one exact job snapshot.

        The snapshot is named by the caller. `latest` is a query convenience
        and belongs to the compatibility layer, not to a command: a command
        that picks its own source can silently analyse something other than
        what the caller was looking at.
        """
        snapshot = self.repo.get_snapshot(job_snapshot_id)
        if snapshot["application_id"] != application_id:
            raise LineageBroken(
                f"job snapshot {job_snapshot_id} does not belong to application {application_id}"
            )
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
            if self._provider is None:
                raise DependencyUnavailable("AI classification was requested but no provider is configured")
            # The provider sees the full deterministic picture as context, but it
            # answers on the narrower proposal contract; deterministic policy decides
            # what survives.
            proposal = self._provider.classify_job(
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
                model=model,
            )
            result = merge_classification(deterministic, proposal, profiles)
            used_provider, used_model = "openai", model
        elif provider != "deterministic":
            raise DependencyUnavailable(f"unsupported provider: {provider}")

        if accept_low_fit:
            # Rebuilt through validation rather than model_copy(update=...), which
            # would skip the model validators that guard this state.
            overrides = {**result.user_override, "fit": "accepted-low-fit"}
            result = JobAnalysis.model_validate({**result.model_dump(mode="json"), "user_override": overrides})

        # Checked before anything is written. An analysis whose Track, Profile,
        # and Emphasis disagree can never produce a draft, so persisting it would
        # only leave the application classified by a combination the engine
        # refuses to act on.
        selected_profile = profiles.get(result.profile)
        if result.track is not selected_profile.track:
            raise StateConflict(
                f"classified Track {result.track.value} and Profile {result.profile.value} "
                f"are inconsistent: {result.profile.value} belongs to Track "
                f"{selected_profile.track.value}"
            )
        if result.emphasis not in selected_profile.allowed_emphases:
            raise StateConflict(
                f"Emphasis {result.emphasis.value} is not allowed for Profile "
                f"{result.profile.value}"
            )

        analysis_id = self.repo.save_analysis(
            application_id,
            snapshot["id"],
            result,
            provider=used_provider,
            model=used_model,
        )
        self.repo.set_normalized_role(application_id, selected_profile.normalized_role)
        return AnalysisResult(analysis_id, result)


class DraftService(ServiceBase):
    """The working draft: generation, manual edits, validation, approval."""

    def draft(self, application_id: str, job_analysis_id: str) -> DraftResult:
        """Build the working draft from one exact analysis.

        The analysis is named by the caller for the same reason the snapshot is
        in `analyze`: a command that resolves `latest` itself can draft from an
        analysis the caller never saw.
        """
        knowledge = self.load_knowledge()
        facts, profiles, policies = knowledge.facts, knowledge.profiles, knowledge.policies
        analysis_id = job_analysis_id
        record = self.repo.get_analysis(analysis_id)
        if record["application_id"] != application_id:
            raise LineageBroken(
                f"analysis {analysis_id} does not belong to application {application_id}"
            )
        analysis = record["analysis"]
        if analysis.fit.value == "low" and analysis.user_override.get("fit") != "accepted-low-fit":
            raise StateConflict("low fit blocks CV generation until --accept-low-fit is recorded")
        unresolved = unresolved_approval_reasons(analysis)
        if unresolved:
            raise StateConflict(
                "ambiguous classification requires an explicit Track/Profile override: "
                f"{unresolved}"
            )
        # The draft is built from the analysis's own snapshot, never from whichever
        # snapshot is newest: a job snapshot added after the analysis describes a
        # job nothing has analyzed yet. `latest_snapshot` is read as a staleness
        # check on the named analysis, not to choose what to draft from.
        latest_snapshot = self.repo.latest_snapshot(application_id)
        if record["job_snapshot_id"] != latest_snapshot["id"]:
            raise StateConflict(
                f"job snapshot {latest_snapshot['id']} is newer than the analysis in hand; "
                "analyze the new snapshot before drafting against it"
            )
        profile = profiles.get(analysis.profile)
        presentation_rules = knowledge.presentations
        draft = build_draft(
            application_id=application_id,
            job_snapshot_id=record["job_snapshot_id"],
            job_analysis_id=analysis_id,
            analysis=analysis,
            profile=profile,
            facts=facts,
            policies=policies,
            candidate=knowledge.candidate,
            presentations=presentation_rules,
        )
        stored = self.artifacts.write_working_draft(draft)
        markdown, manifest = stored.paths.markdown, stored.paths.manifest
        report = validate_draft(
            draft,
            stored.markdown,
            facts,
            profile,
            analysis,
            policies=policies,
            presentations=presentation_rules,
        )
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
        return DraftResult(markdown, manifest, report)

    def validate_working(self, application_id: str) -> ValidationReport:
        knowledge = self.load_knowledge()
        facts, profiles, policies = knowledge.facts, knowledge.profiles, knowledge.policies
        draft = self.artifacts.load_working_draft(application_id)
        _, analysis = self._bound_analysis(application_id, draft, profiles, facts)
        markdown = self.artifacts.working_markdown(application_id)
        if markdown != serialize_markdown(draft):
            try:
                draft = synchronize_markdown_claims(draft, markdown, facts)
            except ValueError:
                pass
            else:
                markdown = self.artifacts.write_working_draft(draft).markdown
        report = validate_draft(
            draft,
            markdown,
            facts,
            profiles.get(draft.profile),
            analysis,
            policies=policies,
            presentations=knowledge.presentations,
        )
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
    ) -> EditResult:
        knowledge = self.load_knowledge()
        facts, profiles, policies = knowledge.facts, knowledge.profiles, knowledge.policies
        draft = self.artifacts.load_working_draft(application_id)
        _, analysis = self._bound_analysis(application_id, draft, profiles, facts)
        updated = apply_claim_edit(
            draft,
            claim_id,
            fact_ids,
            facts,
            text=text,
            template_id=template_id,
            template_version=template_version,
        )
        stored = self.artifacts.write_working_draft(updated)
        report = validate_draft(
            updated,
            stored.markdown,
            facts,
            profiles.get(updated.profile),
            analysis,
            policies=policies,
            presentations=knowledge.presentations,
        )
        self.repo.record_validation(application_id, "manual-claim-edit", report)
        return EditResult(stored.paths.markdown, report)

    def link_claim(self, application_id: str, claim_id: str, text: str, fact_ids: list[str]) -> EditResult:
        return self.edit_claim(application_id, claim_id, fact_ids, text=text)

    def sync_working_claims(self, application_id: str) -> EditResult:
        knowledge = self.load_knowledge()
        facts, profiles, policies = knowledge.facts, knowledge.profiles, knowledge.policies
        draft = self.artifacts.load_working_draft(application_id)
        _, analysis = self._bound_analysis(application_id, draft, profiles, facts)
        updated = synchronize_markdown_claims(
            draft, self.artifacts.working_markdown(application_id), facts
        )
        stored = self.artifacts.write_working_draft(updated)
        report = validate_draft(
            updated,
            stored.markdown,
            facts,
            profiles.get(updated.profile),
            analysis,
            policies=policies,
            presentations=knowledge.presentations,
        )
        self.repo.record_validation(application_id, "manual-markdown-sync", report)
        return EditResult(stored.paths.markdown, report)

    def approve(self, application_id: str) -> ApprovalResult:
        report = self.validate_working(application_id)
        if not report.passed:
            raise ValidationBlocked("approval blocked by pre-render validation", report)
        facts, profiles, _ = self.knowledge()
        draft = self.artifacts.load_working_draft(application_id)
        # The decision record explains the draft being approved, so it is bound to
        # that draft's own analysis. A newer analysis does not get to describe an
        # older document.
        analysis_id, analysis = self._bound_analysis(application_id, draft, profiles, facts)
        existing = [
            row for row in self.repo.artifact_versions(application_id)
            if row["artifact_type"] == "resume_markdown"
        ]
        version = len(existing) + 1
        try:
            published = self.artifacts.publish_working_draft(application_id, version)
        except FileExistsError as exc:
            raise StateConflict(str(exc)) from exc
        markdown_path, manifest_path = published.markdown, published.manifest
        approved_dir = markdown_path.parent
        now = utc_now()
        relative_markdown = self.artifacts.relative(markdown_path)
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
            self.artifacts.relative(manifest_path),
            sha256_file(manifest_path),
            "approved",
            job_snapshot_id=draft.job_snapshot_id,
            track=draft.track.value,
            profile=draft.profile.value,
            emphasis=draft.emphasis.value,
            facts_version=facts.version,
            approved_at=now,
        )
        # The decision record names where rendering will put its outputs, so it
        # asks the artifact store the same question the renderer will.
        expected = self.artifacts.render_targets(
            manifest_path,
            self.renderer.filename_for(
                profiles.get(draft.profile).normalized_role, self.candidate(facts)
            ),
        )
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
                "html": self.artifacts.relative(expected.html),
                "pdf": self.artifacts.relative(expected.pdf),
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
        return ApprovalResult(version, approved_dir, decision_id)


class RenderingService(ServiceBase):
    """Rendering an approved revision and reporting ready state."""

    def render(self, application_id: str) -> RenderResult:
        knowledge = self.load_knowledge()
        facts, profiles, policies = knowledge.facts, knowledge.profiles, knowledge.policies
        manifest_record = self.repo.latest_artifact_version(application_id, "claim_manifest", "approved")
        manifest_path = self.artifacts.resolve(manifest_record["path"])
        draft = self.artifacts.load_draft(manifest_path)
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
            self.artifacts.read_document(self.artifacts.paths_beside(manifest_path).markdown),
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
        targets = self.artifacts.render_targets(
            manifest_path, self.renderer.filename_for(profile.normalized_role, candidate)
        )
        html_path, pdf_path, screenshot_path = targets.html, targets.pdf, targets.screenshot
        self.renderer.render_html(draft, html_path, candidate)
        geometry = self.renderer.render_pdf(html_path, pdf_path, screenshot_path)
        report = self.renderer.validate_rendered(
            draft, profile, html_path, pdf_path, screenshot_path, geometry, candidate
        )
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
                self.artifacts.relative(path),
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
            integrity = verify_ready_integrity(self.artifacts, self._knowledge, self.repo, application_id)
            if not integrity.passed:
                raise ValidationBlocked(
                    "render succeeded but fresh ready integrity verification failed: "
                    f"{[issue.code for issue in integrity.issues]}"
                )
            self.repo.set_ready(application_id, artifact_ids[1], "all ready validation groups passed")
        return RenderResult(pdf_path, report)

    def ready_report(self, application_id: str) -> ValidationReport:
        application = self.repo.get_application(application_id)
        if application["current_status"] != ApplicationStatus.READY.value:
            raise StateConflict("application is not ready")
        return verify_ready_integrity(self.artifacts, self._knowledge, self.repo, application_id)


class TrackingService(ServiceBase):
    """Recruitment-side state: submission and its evidence."""

    def submit(self, application_id: str, reason: str = "submitted to employer") -> SubmissionResult:
        application = self.repo.get_application(application_id)
        if application["current_status"] != ApplicationStatus.READY.value:
            raise StateConflict("applied requires a currently valid ready application")
        integrity = verify_ready_integrity(self.artifacts, self._knowledge, self.repo, application_id)
        if not integrity.passed:
            raise ValidationBlocked(
                "applied blocked by stale or tampered ready state: "
                f"{[issue.code for issue in integrity.issues]}"
            )
        pdf_artifact_version_id = integrity.evidence["pdf_artifact_version_id"]
        self.repo.record_submission(application_id, pdf_artifact_version_id, reason)
        return SubmissionResult(
            application_id,
            pdf_artifact_version_id,
            self.repo.get_application(application_id),
        )
