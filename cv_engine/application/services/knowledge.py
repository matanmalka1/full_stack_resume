from __future__ import annotations

from typing import Any, Generic, TypeVar

from ... import __version__
from ...domain.analysis import classify_job, merge_classification, unresolved_approval_reasons
from ...domain.drafts import (
    apply_claim_edit,
    build_draft,
    serialize_markdown,
    synchronize_markdown_claims,
)
from ...domain.facts import FactStore, FactStoreError
from ...domain.knowledge import Knowledge
from ...domain.models import (
    ApplicationStatus,
    CandidateContext,
    DraftDocument,
    Fact,
    FactStatus,
    JobAnalysis,
    ValidationReport,
)
from ...domain.profiles import ProfileStore
from ...domain.selection import EmphasisPolicyStore
from ...domain.validation import validate_draft
from ...util import sha256_file, utc_now
from ..chain import ChainError, check_draft_chain, decision_record_analysis_id
from ..commands import (
    AnalyzeCommand,
    AnalysisResult,
    ApplicationMutationResult,
    ApprovalResult,
    DraftCommand,
    DraftResult,
    EditResult,
    FactAttachmentResult,
    FactDetailResult,
    FactHistoryResult,
    FactListItem,
    FactListResult,
    FactMutationResult,
    FactReconciliationResult,
    IngestCommand,
    IngestedApplication,
    KnowledgeVersionsResult,
    NextActionCommand,
    RecruitmentStatusCommand,
    RenderResult,
    SubmissionResult,
    fact_event_view,
)
from ..errors import (
    # Re-exported: the v1 CLI and test suite catch WorkflowError from here, and
    # it is bound to the taxonomy's base class, so every refusal below is caught.
    ApplicationError,
    DependencyUnavailable,
    InfrastructureFailure,
    KnowledgeRejected,
    LineageBroken,
    PreconditionFailed,
    StateConflict,
    UnknownRecord,
    ValidationBlocked,
    WorkflowError,
)
from ..ports import (
    ApplicationStore,
    ArtifactStore,
    ClassificationProvider,
    DraftRepository,
    KnowledgeAuditRepository,
    KnowledgeStore,
    PreparationRepository,
    QueryRepository,
    ReadinessRepository,
    Renderer,
    TrackingRepository,
)
from ..queries import (
    ApplicationDetailView,
    ApplicationListView,
    ArtifactVersionsView,
    DecisionRecordView,
    analysis_view,
    application_view,
    artifact_version_view,
    decision_view,
    snapshot_view,
)
from ..ready import verify_ready_integrity


RepoT = TypeVar("RepoT")



from .base import ServiceBase

class KnowledgeService(ServiceBase[KnowledgeAuditRepository]):
    """The fact lifecycle and the knowledge version surface."""

    def knowledge_versions(self) -> KnowledgeVersionsResult:
        """One hash surface per knowledge dependency an artifact can depend on."""
        return KnowledgeVersionsResult.model_validate(self.load_knowledge().versions())

    def list_facts(self, status: str | None = None) -> FactListResult:
        facts = self.fact_store()
        recorded = self.repo.latest_fact_statuses()
        return FactListResult(items=[
            FactListItem(fact=fact, recorded_status=recorded.get(fact.fact_id))
            for fact in facts.by_status(status)
        ])

    def show_fact(self, fact_id: str) -> FactDetailResult:
        facts = self.fact_store()
        try:
            fact = facts.get(fact_id)
        except FactStoreError as exc:
            raise UnknownRecord(str(exc)) from exc
        return FactDetailResult(
            fact=fact,
            events=[fact_event_view(row) for row in self.repo.fact_events(fact_id)],
        )

    def fact_history(self, fact_id: str | None = None) -> FactHistoryResult:
        return FactHistoryResult(
            events=[fact_event_view(row) for row in self.repo.fact_events(fact_id)]
        )

    def _record_fact_event(
        self,
        fact: Fact,
        *,
        event_type: str,
        from_status: str | None,
        reason: str,
        application_id: str | None = None,
        claim_id: str | None = None,
    ) -> FactMutationResult:
        """Persist the fact change's audit record against the reloaded store.

        The store is reloaded from disk first, so the versions written into the
        trail are the ones a later reader will actually find on disk rather than
        the pre-write ones held in memory.
        """
        facts = self.fact_store()
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
        return FactMutationResult(
            fact=fact,
            event_id=event_id,
            facts_version=facts.version,
            lifecycle_version=facts.lifecycle_version,
        )

    def add_fact(
        self,
        source: str,
        payload: dict[str, Any],
        *,
        canonical: bool = False,
        reason: str = "",
        application_id: str | None = None,
        claim_id: str | None = None,
    ) -> FactMutationResult:
        """Create a new fact in its canonical source file and record the event.

        Without `canonical`, the fact lands as `pending` and cannot reach a CV:
        every rendering path resolves facts with `canonical_only=True`.
        """
        try:
            fact = self._knowledge.create_fact(source, payload, canonical=canonical)
        except OSError as exc:
            raise InfrastructureFailure(f"could not store fact: {exc}") from exc
        except (FactStoreError, ValueError) as exc:
            raise KnowledgeRejected(str(exc)) from exc
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
    ) -> FactMutationResult:
        try:
            before, after = self._knowledge.promote_fact(
                fact_id,
                target,
                explicitly_confirmed=explicitly_confirmed,
            )
        except OSError as exc:
            raise InfrastructureFailure(f"could not promote fact: {exc}") from exc
        except (FactStoreError, ValueError) as exc:
            raise KnowledgeRejected(str(exc)) from exc
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
    ) -> FactMutationResult:
        """Turn an unsupported manual claim into a tracked fact.

        This is the product entry point into the lifecycle: a manual edit whose
        wording the fact store cannot support becomes a `pending` claim, and the
        claim's own text becomes the candidate fact rather than being retyped,
        so nothing is strengthened on the way in.
        """
        draft = self.working_draft(application_id)
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

    def attach_fact(
        self, fact_id: str, profile: str, section: str, *, pin: bool = False
    ) -> FactAttachmentResult:
        """Offer a canonical fact to one Profile section's candidate pool."""
        facts, profiles, _ = self.knowledge()
        try:
            fact = facts.get(fact_id, canonical_only=True)
        except FactStoreError as exc:
            raise KnowledgeRejected(
                f"only canonical facts may enter a Profile pool: {exc}"
            ) from exc
        try:
            updated, source = self._knowledge.attach_fact(
                profile, fact_id, section, pin=pin
            )
        except OSError as exc:
            raise InfrastructureFailure(f"could not attach fact: {exc}") from exc
        except (FactStoreError, ValueError) as exc:
            raise KnowledgeRejected(str(exc)) from exc
        # Reload so a Profile that no longer validates against the fact store
        # fails here rather than at the next draft.
        reloaded = self.load_knowledge().profiles
        record = self._record_fact_event(
            fact,
            event_type="fact_attached_to_profile",
            from_status=fact.status.value,
            reason=f"attached to {updated.profile.value} / {section}" + (" (pinned)" if pin else ""),
        )
        return FactAttachmentResult(
            **record.model_dump(),
            profile=updated.profile.value,
            section=section,
            pinned=pin,
            profile_source=source,
            profile_store_version=reloaded.version,
        )

    def reconcile_facts(self) -> FactReconciliationResult:
        """Check the persisted lifecycle against its audit trail.

        Three disagreements matter: a trail entry for a fact that no longer
        exists, a live status that the trail never recorded, and a live status
        that contradicts the last recorded one. Each means a status was changed
        outside the lifecycle, which is exactly what the trail exists to catch.
        """
        facts = self.fact_store()
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
        return FactReconciliationResult(
            passed=not problems,
            fact_counts=counts,
            tracked_facts=len(recorded),
            facts_version=facts.version,
            lifecycle_version=facts.lifecycle_version,
            problems=problems,
        )
