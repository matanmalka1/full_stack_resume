"""§14 document content: AI generation and targeted regeneration.

The user's own edits (autosave) are `editing.py`; nothing there reaches a provider.

Every command names the document by its Application and carries the
`expected_document_hash` the client last read. Generation and regeneration are
Operations: they prepare outside any transaction and activate only while the hash
still matches, so work landing on a document the user changed meanwhile is
discarded rather than written over it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from ....domain.contracts.analysis import JobAnalysis
from ....domain.contracts.base import StrictModel
from ....domain.contracts.drafts import DraftDocument
from ....domain.contracts.knowledge import EmphasisPolicy, Profile, ResumeSectionSpec
from ....domain.contracts.providers import ClaimSupportProposal, ProposedClaim
from ....domain.drafts import (
    draft_claims,
    keep_frame_claims,
    restore_claims,
)
from ....domain.frame import dangling_heading
from ....domain.knowledge import Knowledge
from ...commands import (
    DraftCommand,
    RegenerateClaimCommand,
    RegenerateSectionCommand,
)
from ...errors import (
    PreconditionFailed,
    ProposalRejected,
    ProviderNotConfigured,
    StateConflict,
    UnknownRecord,
)
from ...operations import ClaimReviewReason
from ...ports import (
    AIAttempt,
    AIProvider,
    AssessClaimSupportContext,
    DraftResumeContext,
    RegenerateClaimContext,
    RegenerateSectionContext,
    TransactionManager,
)
from ...ports.analysis_plans import AnalysisContextSourceReader, AnalysisKnowledgeSource
from ...ports.documents import DocumentStore
from ...transactions import assert_external_io_allowed
from ..ai_calls import AICallRunner, RecordedCall
from ..documents import (
    DocumentSource,
    compose_content,
    load_knowledge,
    read_document_source,
    refuse_deleted,
    require_hash,
)
from ..proposals import (
    WithheldClaim,
    apply_proposed_claims,
    fact_context,
    refusal,
    review_semantically,
    withheld_reason,
)
from .inputs import PreparedDraft, PreparedRegeneration

ProposalT = TypeVar("ProposalT", bound=StrictModel)


def _owned() -> bool:
    """A direct call outside the Operation runner has no lease to lose."""
    return True


def _changed_claim_ids(before: DraftDocument, after: DraftDocument) -> set[str]:
    """Claims a proposal wrote: new in `after`, or carrying different text than before.

    What a writer Operation's review covers. A pending line it left exactly as it found
    it belongs to whoever wrote it, not to this Operation's review.
    """
    unchanged = {(claim.claim_id, claim.text) for claim in draft_claims(before)}
    return {
        claim.claim_id
        for claim in draft_claims(after)
        if (claim.claim_id, claim.text) not in unchanged
    }


def _named_claim_ids(draft: DraftDocument, proposed: list[ProposedClaim]) -> set[str]:
    """The lines of `draft` a Proposal answered for; an ID it does not hold names none."""
    held = {claim.claim_id for claim in draft_claims(draft)}
    return {str(claim.claim_id) for claim in proposed if claim.claim_id in held}


def _section_guidance(spec: ResumeSectionSpec) -> dict:
    """What a section's Profile prefers; the writer weighs it, nothing enforces it."""
    return {
        "max_claims": spec.max_claims,
        "min_claims_per_role": spec.min_claims_per_role,
        "min_quantitative_per_role": spec.min_quantitative_per_role,
        "max_claims_per_role": spec.max_claims_per_role,
        "pinned_fact_ids": list(spec.pinned_fact_ids),
    }


def _document_guidance(profile: Profile, policy: EmphasisPolicy) -> dict:
    """What the Profile and Emphasis prefer across sections; guidance only."""
    weights = dict(profile.tag_weights)
    for tag, weight in policy.tag_weights.items():
        weights[tag] = weights.get(tag, 0) + weight
    return {
        "required_tags": list(profile.required_tags),
        "preferred_tags": list(policy.preferred_tags),
        "tag_weights": weights,
        "minimum_preferred_tags": policy.minimum_coverage,
    }


class DraftAuthoringService:
    def __init__(
        self,
        *,
        transactions: TransactionManager,
        documents: DocumentStore,
        sources: AnalysisContextSourceReader,
        knowledge: AnalysisKnowledgeSource,
        provider: AIProvider | None,
        ai_calls: AICallRunner,
    ):
        self.transactions = transactions
        self.documents = documents
        self.sources = sources
        self._knowledge = knowledge
        self._provider = provider
        self.ai_calls = ai_calls

    @property
    def provider(self) -> AIProvider:
        if self._provider is None:
            raise ProviderNotConfigured("AI mode was requested but no provider is configured")
        return self._provider

    def load_knowledge(self) -> Knowledge:
        return load_knowledge(self._knowledge)

    @staticmethod
    def assert_provider_io_allowed() -> None:
        assert_external_io_allowed("draft provider execution")

    def document_source(self, application_id: str) -> DocumentSource:
        with self.transactions.read() as tx:
            return read_document_source(tx, self.documents, self.sources, application_id)

    def _target(self, application_id: str, expected_document_hash: str) -> DocumentSource:
        source = self.document_source(application_id)
        refuse_deleted(application_id, source.deleted_at)
        require_hash(source.document, expected_document_hash)
        return source

    def job_text(self, application_id: str, job_text_hash: str) -> str:
        """The job text the document's analysis read, while it is still the current one.

        An edited job text replaces the earlier one in place, so a document whose
        analysis read the earlier text cannot be drafted from it: analyze the new
        text and build from that analysis first.
        """
        with self.transactions.read() as tx:
            source = self.sources.job_text_source(tx, application_id)
        if source.job_text_hash != job_text_hash:
            raise StateConflict(
                "the job text changed after the document's analysis; analyze the "
                "current text and build from that analysis before drafting"
            )
        return source.job_text

    def _call(
        self,
        operation_id: str,
        invoke: Callable[[], AIAttempt[ProposalT]],
        knowledge: Knowledge,
        still_owned: Callable[[], bool],
    ) -> RecordedCall[ProposalT]:
        """One provider call, every attempt logged against the Operation as it ends."""
        return self.ai_calls.run(
            operation_id,
            invoke,
            knowledge_context_hash=knowledge.context_hash(),
            still_owned=still_owned,
        )

    def prepare(
        self,
        command: DraftCommand,
        *,
        operation_id: str,
        still_owned: Callable[[], bool] = _owned,
    ) -> PreparedDraft:
        """Compose the document's content without changing durable state.

        The engine lays out every section's whole pool as canonical claims, and
        `draft_resume` chooses among them and words the ones it keeps, in one call
        (docs/decisions/ai-owned-selection.md). Every provider attempt is logged against
        `operation_id`; `still_owned` must hold before any retry.
        """
        source = self._target(command.application_id, command.expected_document_hash)
        document = source.document
        if document.content is not None:
            raise PreconditionFailed(
                "the document already has content; edit or regenerate it, or build it "
                "again from its analysis"
            )
        knowledge = self.load_knowledge()
        frame = compose_content(
            command.application_id,
            document.analysis_id,
            source.job_text_hash,
            source.analysis,
            knowledge,
        )
        content, withheld = self._propose_draft(
            operation_id,
            frame,
            source,
            knowledge,
            still_owned=still_owned,
            model=command.model,
            reasoning_effort=command.reasoning_effort,
        )
        return PreparedDraft(
            application_id=command.application_id,
            expected_document_hash=command.expected_document_hash,
            content=content,
            withheld_claims=withheld,
        )

    def _propose_draft(
        self,
        operation_id: str,
        frame: DraftDocument,
        source: DocumentSource,
        knowledge: Knowledge,
        *,
        still_owned: Callable[[], bool],
        model: str | None = None,
        reasoning_effort: str | None = None,
    ) -> tuple[DraftDocument, ClaimReviewReason | None]:
        """`draft_resume`: choose from the frame and word the choice.

        The provider keeps the claims it wants and words them; a claim it leaves out
        is a fact the document does not use. The engine then narrows the frame to the
        kept claims plus every heading, date and contact, in pool order, so each role
        keeps its title, dates and bullets together. A heading left with no bullet
        is refused. Every line comes
        back through `apply_claim_edit`, and wording its facts do not support goes to
        semantic review; a line neither authorizes keeps its frame wording and is
        listed as withheld.
        """
        analysis = source.analysis
        profile = knowledge.profiles.get(analysis.profile)
        specs = {
            (spec.name_he if frame.language == "he" else spec.name_en): spec
            for spec in profile.sections
        }
        pool = sorted(
            {
                fact_id
                for section in frame.sections
                for claim in section.claims
                for fact_id in claim.fact_ids
            }
        )
        job_text = self.job_text(frame.application_id, frame.job_text_hash)
        context = DraftResumeContext(
            job_analysis={
                "track": analysis.track.value,
                "profile": analysis.profile.value,
                "emphasis": frame.emphasis.value,
                "language": analysis.language,
                "keywords": list(analysis.keywords),
            },
            job_text=job_text,
            requirements=[item.model_dump(mode="json") for item in analysis.requirements],
            language=frame.language,
            sections=[
                {
                    "section": section.name,
                    "allowed_fact_ids": sorted(
                        {fact_id for claim in section.claims for fact_id in claim.fact_ids}
                    ),
                    "guidance": _section_guidance(specs[section.name]),
                    "claims": [
                        {
                            "claim_id": claim.claim_id,
                            "style": claim.style,
                            "text": claim.text,
                            "fact_ids": list(claim.fact_ids),
                        }
                        for claim in section.claims
                    ],
                }
                for section in frame.sections
            ],
            allowed_facts=fact_context(knowledge.facts, pool, frame.language),
            guidance=_document_guidance(profile, knowledge.policies.get(frame.emphasis)),
        )
        written = self._call(
            operation_id,
            lambda: self.provider.draft_resume(
                context, model=model, reasoning_effort=reasoning_effort
            ),
            knowledge,
            still_owned,
        )
        proposed = written.proposal.claims
        kept = {str(claim.claim_id) for claim in proposed if claim.claim_id is not None}
        chosen = keep_frame_claims(frame, profile, kept)
        for section in chosen.sections:
            empty = dangling_heading(section.claims)
            if empty is not None:
                raise ProposalRejected(
                    f"draft_resume kept no bullet under {empty!r} in {section.name}",
                    unsupported=[],
                )
        updated, withheld = apply_proposed_claims(
            chosen, proposed, knowledge.facts, set(pool), task="draft_resume"
        )
        updated, _review, reason = self._review_and_settle(
            operation_id,
            chosen,
            updated,
            withheld,
            knowledge,
            sorted({fact_id for claim in draft_claims(updated) for fact_id in claim.fact_ids}),
            still_owned=still_owned,
            proposed_ids=_named_claim_ids(chosen, proposed),
            model=model,
            reasoning_effort=reasoning_effort,
        )
        return updated, reason

    def _regeneration_target(
        self, application_id: str, expected_document_hash: str
    ) -> tuple[DocumentSource, DraftDocument, Knowledge]:
        """The exact document a regeneration named, or the refusal that says why."""
        source = self._target(application_id, expected_document_hash)
        if source.document.content is None:
            raise PreconditionFailed("the document has no content to regenerate yet")
        return source, source.document.content, self.load_knowledge()

    def _review_pending_claims(
        self,
        operation_id: str,
        draft: DraftDocument,
        knowledge: Knowledge,
        selected: list[str],
        *,
        still_owned: Callable[[], bool],
        claim_ids: set[str],
        model: str | None,
        reasoning_effort: str | None,
    ) -> tuple[DraftDocument, RecordedCall[ClaimSupportProposal] | None, list[WithheldClaim]]:
        """Semantic review of the pending claims among `claim_ids` - only those.

        A pending line the Operation did not touch is not its to authorize or to fail on.
        A line the review does not authorize comes back still pending, with its reason.
        """
        pending_ids = {
            claim.claim_id
            for claim in draft_claims(draft)
            if claim.claim_type == "pending" and claim.claim_id in claim_ids
        }
        if not pending_ids:
            return draft, None, []
        claims = [
            {
                "claim_id": claim.claim_id,
                "section": section.name,
                "text": claim.text,
                "fact_ids": list(claim.fact_ids),
            }
            for section in draft.sections
            for claim in section.claims
            if claim.claim_id in pending_ids
        ]
        context = AssessClaimSupportContext(
            language=draft.language,
            claims=claims,
            allowed_facts=fact_context(knowledge.facts, selected, draft.language),
        )
        # A separate call from the writer's: retrying the review never repeats it.
        review = self._call(
            operation_id,
            lambda: self.provider.assess_claim_support(
                context, model=model, reasoning_effort=reasoning_effort
            ),
            knowledge,
            still_owned,
        )
        authorized, withheld = review_semantically(
            draft, review, knowledge.facts, claim_ids=pending_ids
        )
        return authorized, review, withheld

    def _review_and_settle(
        self,
        operation_id: str,
        before: DraftDocument,
        applied: DraftDocument,
        withheld: list[WithheldClaim],
        knowledge: Knowledge,
        selected: list[str],
        *,
        still_owned: Callable[[], bool],
        proposed_ids: set[str],
        review_ids: set[str] | None = None,
        model: str | None,
        reasoning_effort: str | None,
    ) -> tuple[DraftDocument, RecordedCall[ClaimSupportProposal] | None, ClaimReviewReason | None]:
        """Review what the writer changed, withhold what is not authorized, or refuse.

        `before` is the document the proposal was applied to and `applied` the result.
        Every withheld line - refused by the edit path, or not authorized by review -
        goes back to exactly its `before` form, so none of its proposed wording or links
        reaches the document. What survives is written; the withheld lines travel with
        it as the Operation's `withheld_claims`.

        Only when every line in `proposed_ids` - the lines the answer named that
        `before` holds, echoed ones included - is withheld does the Operation fail:
        nothing of the answer is left to write.

        Review covers the lines the writer changed; `review_ids` names them instead when
        there was no writer, as for the user's own wording.
        """
        reviewed, review, review_withheld = self._review_pending_claims(
            operation_id,
            applied,
            knowledge,
            selected,
            still_owned=still_owned,
            claim_ids=_changed_claim_ids(before, applied) if review_ids is None else review_ids,
            model=model,
            reasoning_effort=reasoning_effort,
        )
        withheld = [*withheld, *review_withheld]
        withheld_ids = {item.claim_id for item in withheld}
        settled = restore_claims(reviewed, before, withheld_ids)
        if withheld and proposed_ids <= withheld_ids:
            raise refusal(settled, withheld, knowledge.facts)
        reason = withheld_reason(settled, withheld, knowledge.facts) if withheld else None
        return settled, review, reason

    def prepare_section_regeneration(
        self,
        command: RegenerateSectionCommand,
        *,
        operation_id: str,
        still_owned: Callable[[], bool] = _owned,
    ) -> PreparedRegeneration:
        """§14 `regenerate_section`: propose replacement wording for one section."""
        source, draft, knowledge = self._regeneration_target(
            command.application_id, command.expected_document_hash
        )
        analysis = source.analysis
        section = next((item for item in draft.sections if item.name == command.section), None)
        if section is None:
            raise UnknownRecord(f"unknown section in the document: {command.section}")
        allowed = sorted({fact_id for claim in section.claims for fact_id in claim.fact_ids})
        context = RegenerateSectionContext(
            section=section.name,
            language=draft.language,
            job_analysis=self._analysis_context(analysis),
            current_claims=[
                {
                    "claim_id": claim.claim_id,
                    "text": claim.text,
                    "fact_ids": list(claim.fact_ids),
                }
                for claim in section.claims
            ],
            allowed_facts=fact_context(knowledge.facts, allowed, draft.language),
            instruction=command.instruction,
        )
        written = self._call(
            operation_id,
            lambda: self.provider.regenerate_section(
                context, model=command.model, reasoning_effort=command.reasoning_effort
            ),
            knowledge,
            still_owned,
        )
        proposed = written.proposal
        if proposed.section != section.name:
            raise ProposalRejected(
                f"regenerate_section answered for section {proposed.section!r}, not {section.name!r}"
            )
        updated, withheld = apply_proposed_claims(
            draft, proposed.claims, knowledge.facts, set(allowed), task="regenerate_section"
        )
        named = _named_claim_ids(draft, proposed.claims)
        updated, _review, reason = self._review_and_settle(
            operation_id,
            draft,
            updated,
            withheld,
            knowledge,
            allowed,
            still_owned=still_owned,
            proposed_ids=named,
            model=command.model,
            reasoning_effort=command.reasoning_effort,
        )
        kept_back = set() if reason is None else {item.claim_id for item in reason.claims}
        return PreparedRegeneration(
            application_id=command.application_id,
            expected_document_hash=command.expected_document_hash,
            content=updated,
            claim_ids=[
                str(claim.claim_id)
                for claim in proposed.claims
                if claim.claim_id in named and claim.claim_id not in kept_back
            ],
            ai_call_id=written.ai_call_id,
            withheld_claims=reason,
        )

    def prepare_claim_regeneration(
        self,
        command: RegenerateClaimCommand,
        *,
        operation_id: str,
        still_owned: Callable[[], bool] = _owned,
    ) -> PreparedRegeneration:
        """§14 `regenerate_claim`: propose replacement wording for one claim."""
        source, draft, knowledge = self._regeneration_target(
            command.application_id, command.expected_document_hash
        )
        analysis = source.analysis
        located = next(
            (
                (section, claim)
                for section in draft.sections
                for claim in section.claims
                if claim.claim_id == command.claim_id
            ),
            None,
        )
        if located is None:
            raise UnknownRecord(f"unknown claim in the document: {command.claim_id}")
        section, claim = located
        allowed = sorted(claim.fact_ids)
        if command.keep_text:
            # The user's own wording, reviewed as written: the reviewer is the only
            # provider call, and its evidence is the Operation's evidence. Review decides
            # nothing on its own - `review_semantically` applies the same hard checks it
            # applies to writer output. One line, so a line withheld is a refusal.
            if claim.claim_type != "pending" or not claim.fact_ids:
                raise ProposalRejected(
                    "only a pending claim linked to at least one fact can have its own wording reviewed"
                )
            reviewed, review, _reason = self._review_and_settle(
                operation_id,
                draft,
                draft,
                [],
                knowledge,
                allowed,
                still_owned=still_owned,
                proposed_ids={claim.claim_id},
                review_ids={claim.claim_id},
                model=command.model,
                reasoning_effort=command.reasoning_effort,
            )
            if review is None:
                raise ProposalRejected("semantic review produced no evidence")
            return PreparedRegeneration(
                application_id=command.application_id,
                expected_document_hash=command.expected_document_hash,
                content=reviewed,
                claim_ids=[claim.claim_id],
                ai_call_id=review.ai_call_id,
            )
        context = RegenerateClaimContext(
            claim_id=claim.claim_id,
            section=section.name,
            language=draft.language,
            job_analysis=self._analysis_context(analysis),
            current_text=claim.text,
            allowed_facts=fact_context(knowledge.facts, allowed, draft.language),
            instruction=command.instruction,
        )
        written = self._call(
            operation_id,
            lambda: self.provider.regenerate_claim(
                context, model=command.model, reasoning_effort=command.reasoning_effort
            ),
            knowledge,
            still_owned,
        )
        proposed = written.proposal
        if proposed.claim_id != claim.claim_id:
            raise ProposalRejected(
                f"regenerate_claim answered for claim {proposed.claim_id!r}, not {claim.claim_id!r}"
            )
        updated, withheld = apply_proposed_claims(
            draft,
            [
                ProposedClaim(
                    section=section.name,
                    claim_id=proposed.claim_id,
                    text=proposed.text,
                    fact_ids=list(proposed.fact_ids),
                )
            ],
            knowledge.facts,
            set(allowed),
            task="regenerate_claim",
        )
        # One line: withheld means refused, so nothing is ever written partially here.
        updated, _review, _reason = self._review_and_settle(
            operation_id,
            draft,
            updated,
            withheld,
            knowledge,
            allowed,
            still_owned=still_owned,
            proposed_ids={proposed.claim_id},
            model=command.model,
            reasoning_effort=command.reasoning_effort,
        )
        return PreparedRegeneration(
            application_id=command.application_id,
            expected_document_hash=command.expected_document_hash,
            content=updated,
            claim_ids=[proposed.claim_id],
            ai_call_id=written.ai_call_id,
        )

    @staticmethod
    def _analysis_context(analysis: JobAnalysis) -> dict:
        """The narrow analysis view a wording task needs.

        Requirements are relevant writing context; Fit and approval routing remain policy.
        """
        return {
            "track": analysis.track.value,
            "profile": analysis.profile.value,
            "emphasis": analysis.emphasis.value,
            "language": analysis.language,
            "keywords": list(analysis.keywords),
            "requirements": [item.model_dump(mode="json") for item in analysis.requirements],
        }
