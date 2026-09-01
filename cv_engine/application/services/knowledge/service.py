"""The fact lifecycle: the commands that move a fact and the reads over it.

Every command here stages its Knowledge file, builds the audit actions the
mutation will carry, and hands both to the two-phase engine in `mutations`.
What stays in this module is what a lifecycle change touches: which transitions
are allowed, what a fact event records, and what each command returns.
"""

from __future__ import annotations

from typing import Any

from ....domain.facts import FactStoreError
from ....domain.models import (
    Fact,
    FactStatus,
)
from ....domain.selection import MissingFactRendering as DomainMissingFactRendering
from ....domain.selection import build_selection
from ....util import new_id, utc_now
from ...commands import (
    ConfirmAndUseFactResult,
    FactAttachmentResult,
    FactDetailResult,
    FactHistoryResult,
    FactListItem,
    FactListResult,
    FactMutationResult,
    FactReconciliationResult,
    KnowledgeVersionsResult,
    fact_event_view,
)
from ...errors import (
    # Re-exported: the API and test suite catch WorkflowError from here, and
    # it is bound to the taxonomy's base class, so every refusal below is caught.
    InfrastructureFailure,
    KnowledgeRejected,
    MissingFactRendering,
    UnknownRecord,
)
from ...knowledge_mutations import PrepareKnowledgeMutation
from ..base import working_draft_document
from .mutations import KnowledgeMutationEngine


class KnowledgeService(KnowledgeMutationEngine):
    """The fact lifecycle and the knowledge version surface.

    The mutation engine is a base rather than a collaborator: `add_fact`,
    `attach_fact`, and `confirm_and_use_fact` reach `_complete_prepared`
    through `self`, which is the seam the crash-recovery tests replace.
    """

    def knowledge_versions(self) -> KnowledgeVersionsResult:
        """One hash surface per knowledge dependency an artifact can depend on."""
        return KnowledgeVersionsResult.model_validate(self.load_knowledge().versions())

    def list_facts(self, status: str | None = None) -> FactListResult:
        facts = self.fact_store()
        recorded = self.repo.latest_fact_statuses()
        return FactListResult(
            items=[
                FactListItem(fact=fact, recorded_status=recorded.get(fact.fact_id))
                for fact in facts.by_status(status)
            ]
        )

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

    def _fact_event_action(
        self,
        fact: Fact,
        *,
        event_type: str,
        from_status: str | None,
        reason: str,
        facts_version: str,
        lifecycle_version: str,
        application_id: str | None = None,
        claim_id: str | None = None,
    ) -> dict[str, Any]:
        return {
            "type": "fact_event",
            "event_id": new_id(),
            "created_at": utc_now(),
            "fact_id": fact.fact_id,
            "source_file": fact.source_file,
            "event_type": event_type,
            "from_status": from_status,
            "to_status": fact.status.value,
            "fact": fact.model_dump(mode="json"),
            "facts_version": facts_version,
            "lifecycle_version": lifecycle_version,
            "reason": reason,
            "application_id": application_id,
            "claim_id": claim_id,
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
    ) -> FactMutationResult:
        """Create a new fact in its canonical source file and record the event.

        Without `canonical`, the fact lands as `pending` and cannot reach a CV:
        every rendering path resolves facts with `canonical_only=True`.
        """
        self._ensure_mutations_allowed()
        mutation_id = new_id()
        try:
            staged, fact = self._knowledge.stage_create_fact(
                mutation_id, source, payload, canonical=canonical
            )
        except OSError as exc:
            raise InfrastructureFailure(f"could not store fact: {exc}") from exc
        except (FactStoreError, ValueError) as exc:
            raise KnowledgeRejected(str(exc)) from exc
        action = self._fact_event_action(
            fact,
            event_type="fact_created",
            from_status=None,
            reason=reason
            or ("explicitly confirmed on creation" if canonical else "new pending fact"),
            facts_version=staged.proposed_versions["facts"],
            lifecycle_version=staged.proposed_versions["facts_lifecycle"],
            application_id=application_id,
            claim_id=claim_id,
        )
        return self._run_fact_mutation(staged, fact, action)

    def create_pending_fact(
        self,
        source: str,
        payload: dict[str, Any],
        *,
        reason: str = "",
        application_id: str | None = None,
        claim_id: str | None = None,
    ) -> FactMutationResult:
        if payload.get("fact_id"):
            raise KnowledgeRejected("fact identity is generated and is not user-editable")
        return self.add_fact(
            source,
            {**payload, "fact_id": new_id()},
            canonical=False,
            reason=reason,
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
        self._ensure_mutations_allowed()
        mutation_id = new_id()
        try:
            staged, before, after = self._knowledge.stage_promote_fact(
                mutation_id,
                fact_id,
                target,
                explicitly_confirmed=explicitly_confirmed,
            )
        except OSError as exc:
            raise InfrastructureFailure(f"could not promote fact: {exc}") from exc
        except (FactStoreError, ValueError) as exc:
            raise KnowledgeRejected(str(exc)) from exc
        action = self._fact_event_action(
            after,
            event_type="fact_promoted",
            from_status=before.status.value,
            reason=reason or f"explicit promotion to {after.status.value}",
            facts_version=staged.proposed_versions["facts"],
            lifecycle_version=staged.proposed_versions["facts_lifecycle"],
        )
        return self._run_fact_mutation(staged, after, action)

    def transition_fact(
        self,
        fact_id: str,
        command: str,
        *,
        explicitly_confirmed: bool,
        reason: str = "",
    ) -> FactMutationResult:
        targets = {"confirm": FactStatus.CONFIRMED, "promote": FactStatus.CANONICAL}
        try:
            target = targets[command]
        except KeyError as exc:
            raise KnowledgeRejected(f"unknown fact transition command: {command}") from exc
        if not explicitly_confirmed:
            raise KnowledgeRejected(f"promotion to {target.value} requires explicit confirmation")
        return self.promote_fact(
            fact_id,
            target.value,
            explicitly_confirmed=True,
            reason=reason,
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
        draft = working_draft_document(self.repo, application_id)
        claims = [
            draft.headline,
            *draft.contacts,
            *(claim for section in draft.sections for claim in section.claims),
        ]
        try:
            claim = next(item for item in claims if item.claim_id == claim_id)
        except StopIteration as exc:
            raise UnknownRecord(f"unknown claim in the working draft: {claim_id}") from exc
        if claim.style == "headline" or claim.claim_type == "headline":
            raise KnowledgeRejected(
                "the document headline is not a factual claim and cannot become a fact"
            )
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
                "provenance": provenance
                or (
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

    def create_fact_from_claim(
        self,
        application_id: str,
        claim_id: str,
        *,
        source: str,
        meaning: str,
        tags: list[str],
        english: str | None = None,
        hebrew: str | None = None,
        provenance: str | None = None,
        effective_dates: str | None = None,
        replaces: str | None = None,
        reason: str = "",
    ) -> FactMutationResult:
        return self.capture_claim_fact(
            application_id,
            claim_id,
            source=source,
            fact_id=new_id(),
            meaning=meaning,
            tags=tags,
            english=english,
            hebrew=hebrew,
            provenance=provenance,
            effective_dates=effective_dates,
            replaces=replaces,
            canonical=False,
            reason=reason,
        )

    def attach_fact(
        self, fact_id: str, profile: str, section: str, *, pin: bool = False
    ) -> FactAttachmentResult:
        """Offer a canonical fact to one Profile section's candidate pool."""
        self._ensure_mutations_allowed()
        facts, _profiles, _ = self.knowledge()
        try:
            fact = facts.get(fact_id, canonical_only=True)
        except FactStoreError as exc:
            raise KnowledgeRejected(
                f"only canonical facts may enter a Profile pool: {exc}"
            ) from exc
        mutation_id = new_id()
        try:
            staged, updated, source = self._knowledge.stage_attach_fact(
                mutation_id, profile, fact_id, section, pin=pin
            )
        except OSError as exc:
            raise InfrastructureFailure(f"could not attach fact: {exc}") from exc
        except (FactStoreError, ValueError) as exc:
            raise KnowledgeRejected(str(exc)) from exc
        action = self._fact_event_action(
            fact,
            event_type="fact_attached_to_profile",
            from_status=fact.status.value,
            reason=f"attached to {updated.profile.value} / {section}"
            + (" (pinned)" if pin else ""),
            facts_version=staged.proposed_versions["facts"],
            lifecycle_version=staged.proposed_versions["facts_lifecycle"],
        )
        record = self._run_fact_mutation(staged, fact, action)
        return FactAttachmentResult(
            **record.model_dump(),
            profile=updated.profile.value,
            section=section,
            pinned=pin,
            profile_source=source,
            profile_store_version=staged.proposed_versions["profiles"],
        )

    def confirm_and_use_fact(
        self,
        fact_id: str,
        *,
        application_id: str,
        job_analysis_id: str,
        profile: str,
        section: str,
        reason: str = "",
    ) -> ConfirmAndUseFactResult:
        """Promote, attach, and select one pending fact as one recoverable command."""
        self._ensure_mutations_allowed()
        try:
            analysis_record = self.repo.get_analysis(job_analysis_id)
        except UnknownRecord as exc:
            raise UnknownRecord(str(exc)) from exc
        if analysis_record["application_id"] != application_id:
            raise KnowledgeRejected("job analysis belongs to another application")
        analysis = analysis_record["analysis"]
        if analysis.profile.value != profile:
            raise KnowledgeRejected(
                f"analysis Profile {analysis.profile.value} does not match requested {profile}"
            )

        mutation_id = new_id()
        try:
            (
                staged_files,
                before,
                confirmed,
                canonical,
                _updated_profile,
                _profile_source,
                proposed,
            ) = self._knowledge.stage_confirm_and_use_fact(mutation_id, fact_id, profile, section)
            selected_profile = proposed.profiles.get(profile)
            _selected, manifest = build_selection(
                analysis=analysis,
                profile=selected_profile,
                policy=proposed.policies.get(analysis.emphasis),
                policy_store_version=proposed.policies.version,
                facts=proposed.facts,
                line_groups=(
                    proposed.presentations.line_groups(selected_profile, analysis.emphasis)
                    if proposed.presentations is not None
                    else None
                ),
            )
            if fact_id not in manifest.selected_fact_ids:
                raise ValueError("confirmed fact was not selected by the replacement plan")
        except OSError as exc:
            raise InfrastructureFailure(f"could not prepare Knowledge mutation: {exc}") from exc
        except DomainMissingFactRendering as exc:
            if "staged_files" in locals():
                for staged in staged_files:
                    self._knowledge.discard_staged(staged)
            raise MissingFactRendering(exc.fact_id, exc.language) from exc
        except (FactStoreError, ValueError) as exc:
            if "staged_files" in locals():
                for staged in staged_files:
                    self._knowledge.discard_staged(staged)
            raise KnowledgeRejected(str(exc)) from exc

        facts_version = proposed.facts.version
        lifecycle_version = proposed.facts.lifecycle_version
        actions = [
            self._fact_event_action(
                confirmed,
                event_type="fact_promoted",
                from_status=before.status.value,
                reason=reason or "explicit promotion to confirmed",
                facts_version=facts_version,
                lifecycle_version=lifecycle_version,
                application_id=application_id,
            ),
            self._fact_event_action(
                canonical,
                event_type="fact_promoted",
                from_status=confirmed.status.value,
                reason=reason or "explicit promotion to canonical",
                facts_version=facts_version,
                lifecycle_version=lifecycle_version,
                application_id=application_id,
            ),
            self._fact_event_action(
                canonical,
                event_type="fact_attached_to_profile",
                from_status=canonical.status.value,
                reason=f"attached to {profile} / {section} (pinned)",
                facts_version=facts_version,
                lifecycle_version=lifecycle_version,
                application_id=application_id,
            ),
        ]
        plan_id = new_id()
        plan_created_at = utc_now()
        actions.append(
            {
                "type": "selection_plan",
                "plan_id": plan_id,
                "application_id": application_id,
                "job_analysis_id": job_analysis_id,
                "plan": manifest.model_dump(mode="json"),
                "candidate_context_version": proposed.candidate.context_version,
                "candidate_context_hash": proposed.candidate.version_hash,
                "profile_version": proposed.profiles.version,
                "selection_policy_version": proposed.policies.version,
                "track_emphasis_dependencies": {
                    "track": analysis.track.value,
                    "emphasis": analysis.emphasis.value,
                },
                "created_at": plan_created_at,
            }
        )
        payload = {
            "knowledge_files": [self._stored_staged_file(staged) for staged in staged_files[1:]],
            "actions": actions,
        }
        primary = staged_files[0]
        request = PrepareKnowledgeMutation(
            mutation_id=mutation_id,
            mutation_type="confirm_and_use_fact",
            source_reference=primary.source_reference,
            staged_reference=primary.staged_reference,
            old_sha256=primary.old_sha256,
            new_sha256=primary.new_sha256,
            db_mutation_type="selection_plan",
            db_mutation_id=plan_id,
            db_mutation=payload,
            recovery_strategy="finish_or_restore",
        )
        try:
            mutation = self.repo.prepare_knowledge_mutation(request)
        except Exception:
            for staged in staged_files:
                self._knowledge.discard_staged(staged)
            raise
        self._complete_prepared(mutation)
        return ConfirmAndUseFactResult(
            fact=canonical,
            event_ids=[action["event_id"] for action in actions if action["type"] == "fact_event"],
            selection_plan=self.repo.selection_plan(plan_id),
            facts_version=facts_version,
            lifecycle_version=lifecycle_version,
            profile_store_version=proposed.profiles.version,
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
            fact.fact_id
            for fact in facts.by_status()
            if fact.status is not FactStatus.CANONICAL and fact.fact_id not in recorded
        ]
        problems.extend(
            f"non-canonical fact has no lifecycle event: {fact_id}" for fact_id in untracked
        )
        prepared = self.repo.prepared_knowledge_mutations()
        quarantined = self.repo.quarantined_knowledge_mutations()
        problems.extend(
            f"Knowledge mutation still requires recovery: {mutation.id}" for mutation in prepared
        )
        problems.extend(
            f"Knowledge mutation is quarantined: {mutation.id} ({mutation.quarantine_reason})"
            for mutation in quarantined
        )
        counts = {status.value: len(facts.by_status(status)) for status in FactStatus}
        return FactReconciliationResult(
            passed=not problems,
            fact_counts=counts,
            tracked_facts=len(recorded),
            facts_version=facts.version,
            lifecycle_version=facts.lifecycle_version,
            problems=problems,
            journal_prepared=len(prepared),
            journal_quarantined=len(quarantined),
        )
