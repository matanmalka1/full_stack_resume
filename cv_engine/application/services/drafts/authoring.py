"""§14 document content: generation, autosave, and targeted regeneration.

Every command names the document by its Application and carries the
`expected_document_hash` the client last read. Generation and regeneration are
Operations: they prepare outside any transaction and activate only while the hash
still matches, so work landing on a document the user changed meanwhile is
discarded rather than written over it.
"""

from __future__ import annotations

from ....domain.contracts.analysis import JobAnalysis
from ....domain.contracts.drafts import DraftDocument
from ....domain.contracts.knowledge import EmphasisPolicy, Profile, ResumeSectionSpec
from ....domain.contracts.providers import ProposedClaim
from ....domain.document import content_check, preparation_state
from ....domain.drafts import (
    add_claim,
    apply_claim_edit,
    draft_claims,
    keep_frame_claims,
    remove_claim,
    reorder_draft,
)
from ....domain.frame import dangling_heading
from ....domain.knowledge import Knowledge
from ....util import utc_now
from ...commands import (
    DocumentMutationResult,
    DraftCommand,
    RegenerateClaimCommand,
    RegenerateSectionCommand,
    RegenerationResult,
    UpdateDocumentCommand,
)
from ...errors import (
    ApplicationError,
    InfrastructureFailure,
    PreconditionFailed,
    ProposalRejected,
    ProviderNotConfigured,
    UnknownRecord,
)
from ...ports import (
    AIProvider,
    AssessClaimSupportContext,
    DraftResumeContext,
    RegenerateClaimContext,
    RegenerateSectionContext,
    SnapshotPayloadStore,
    TransactionManager,
)
from ...ports.analysis_plans import AnalysisContextSourceReader, AnalysisKnowledgeSource
from ...ports.documents import DocumentBody, DocumentStore
from ...ports.drafts import DraftEvidencePreserver
from ...transactions import assert_external_io_allowed
from ..documents import (
    DocumentSource,
    compose_content,
    current_basis,
    load_knowledge,
    read_document_source,
    refuse_deleted,
    require_hash,
)
from ..proposals import (
    ProviderEvidence,
    apply_proposed_claims,
    authorize_semantically_reviewed_claims,
    evidence_attached,
    fact_context,
)
from .activation import DraftActivation
from .inputs import PreparedDraft, PreparedRegeneration


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
        evidence: DraftEvidencePreserver,
        snapshot_payloads: SnapshotPayloadStore | None = None,
    ):
        self.transactions = transactions
        self.documents = documents
        self.sources = sources
        self._knowledge = knowledge
        self._provider = provider
        self.evidence = evidence
        self.snapshot_payloads = snapshot_payloads
        self.activation = DraftActivation(documents)

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

    def snapshot_source(self, snapshot_id: str) -> dict:
        with self.transactions.read() as tx:
            analysis_source = self.sources.analysis_source(tx, snapshot_id)
        return {
            "id": analysis_source.job_snapshot_id,
            "payload_path": analysis_source.payload_path,
            "source_hash": analysis_source.source_hash,
        }

    def preserve(self, application_id, operation_id, task, provenance):
        return self.evidence.preserve(application_id, operation_id, task, provenance)

    def activate_regeneration(self, prepared: PreparedRegeneration) -> RegenerationResult:
        with self.transactions.write() as tx:
            return self.activation.activate_regeneration(tx, prepared)

    def prepare(self, command: DraftCommand, *, operation_id: str) -> PreparedDraft:
        """Compose the document's content without changing durable state.

        The engine lays out every section's whole pool as canonical claims, and
        `draft_resume` chooses among them and words the ones it keeps, in one call
        (docs/decisions/ai-owned-selection.md). `operation_id` is where every
        sanitized response is preserved.
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
            source.job_snapshot_id,
            source.analysis,
            knowledge,
        )
        content, evidence, review_evidence = self._propose_draft(
            command.application_id,
            operation_id,
            frame,
            source,
            knowledge,
            model=command.model,
            reasoning_effort=command.reasoning_effort,
        )
        return PreparedDraft(
            application_id=command.application_id,
            expected_document_hash=command.expected_document_hash,
            content=content,
            evidence=evidence,
            review_evidence=review_evidence,
        )

    def _propose_draft(
        self,
        application_id: str,
        operation_id: str,
        frame: DraftDocument,
        source: DocumentSource,
        knowledge: Knowledge,
        *,
        model: str | None = None,
        reasoning_effort: str | None = None,
    ) -> tuple[DraftDocument, ProviderEvidence, ProviderEvidence | None]:
        """`draft_resume`: choose from the frame and word the choice.

        The provider keeps the claims it wants and words them; a claim it leaves out
        is a fact the document does not use. The engine then narrows the frame to the
        kept claims plus every heading, date and contact, in pool order, so each role
        keeps its title, dates and bullets together. A heading left with no bullet
        is refused. Every line comes
        back through `apply_claim_edit`, and wording its facts do not support goes to
        semantic review or is refused as `ProposalRejected`.
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
        snapshot = self.snapshot_source(frame.job_snapshot_id)
        job_text = ""
        if self.snapshot_payloads is not None and snapshot.get("payload_path"):
            try:
                job_text = self.snapshot_payloads.read_snapshot(
                    snapshot["payload_path"], snapshot["source_hash"]
                )
            except (OSError, ValueError) as exc:
                raise InfrastructureFailure(f"could not read job snapshot payload: {exc}") from exc
        answered = self.provider.draft_resume(
            DraftResumeContext(
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
            ),
            model=model,
            reasoning_effort=reasoning_effort,
        )
        evidence = self.preserve(application_id, operation_id, "draft_resume", answered.provenance)
        proposed = answered.proposal.claims
        with evidence_attached(evidence):
            kept = {str(claim.claim_id) for claim in proposed if claim.claim_id is not None}
            chosen = keep_frame_claims(frame, profile, kept)
            for section in chosen.sections:
                empty = dangling_heading(section.claims)
                if empty is not None:
                    raise ProposalRejected(
                        f"draft_resume kept no bullet under {empty!r} in {section.name}",
                        unsupported=[],
                    )
            updated = apply_proposed_claims(
                chosen,
                proposed,
                knowledge.facts,
                set(pool),
                task="draft_resume",
                allow_semantic_review=True,
            )
        updated, review_evidence = self._review_pending_claims(
            application_id,
            operation_id,
            updated,
            knowledge,
            sorted({fact_id for claim in draft_claims(updated) for fact_id in claim.fact_ids}),
            evidence,
            claim_ids=_changed_claim_ids(chosen, updated),
            model=model,
            reasoning_effort=reasoning_effort,
        )
        return (updated, evidence, review_evidence)

    def update_document(self, command: UpdateDocumentCommand) -> DocumentMutationResult:
        """§14 autosave: apply one structured patch against one exact hash.

        The whole patch commits as a single write. Nothing here validates: §15 owns
        the content report, and a check on every keystroke would make a passed report
        mean "recently saved" instead of "recently checked". Editing an approved or
        ready document is allowed; it changes the basis, so the document returns to
        draft on the next read.
        """
        source = self._target(command.application_id, command.expected_document_hash)
        document = source.document
        if document.content is None:
            raise PreconditionFailed("the document has no content to edit yet; create a draft")
        knowledge = self.load_knowledge()
        facts = knowledge.facts
        patched = document.content
        for edit in command.claim_edits:
            try:
                patched = apply_claim_edit(
                    patched,
                    edit.claim_id,
                    list(edit.fact_ids),
                    facts,
                    text=edit.text,
                    template_id=edit.template_id,
                    template_version=edit.template_version,
                )
            except KeyError as exc:
                raise UnknownRecord(f"unknown claim in the document: {edit.claim_id}") from exc
            except ValueError as exc:
                raise PreconditionFailed(f"claim edit rejected: {exc}") from exc
        for claim_id in command.claim_removals:
            try:
                patched = remove_claim(patched, claim_id)
            except KeyError as exc:
                raise UnknownRecord(f"unknown claim in the document: {claim_id}") from exc
            except ValueError as exc:
                raise PreconditionFailed(f"claim removal rejected: {exc}") from exc
        added_claim_ids: set[str] = set()
        for addition in command.claim_additions:
            try:
                patched, new_claim_id = add_claim(patched, addition.section, addition.text)
            except KeyError as exc:
                raise UnknownRecord(f"unknown section in the document: {addition.section}") from exc
            except ValueError as exc:
                raise PreconditionFailed(f"claim addition rejected: {exc}") from exc
            added_claim_ids.add(new_claim_id)
        try:
            patched = reorder_draft(patched, claim_orders=command.claim_orders)
        except KeyError as exc:
            raise UnknownRecord(f"unknown section in the document: {exc.args[0]}") from exc
        except ValueError as exc:
            raise PreconditionFailed(f"document reorder rejected: {exc}") from exc
        with self.transactions.write() as tx:
            updated = self.documents.update_body(
                tx,
                command.application_id,
                command.expected_document_hash,
                DocumentBody(analysis_id=document.analysis_id, content=patched),
                updated_at=utc_now(),
            )
        edited = {edit.claim_id for edit in command.claim_edits} | added_claim_ids
        new_basis = current_basis(updated, knowledge)
        return DocumentMutationResult(
            application_id=command.application_id,
            document_id=updated.id,
            document_hash=updated.document_hash,
            preparation_state=preparation_state(updated, new_basis),
            content_check=content_check(updated, new_basis),
            pending_claim_ids=sorted(
                claim.claim_id
                for claim in draft_claims(patched)
                if claim.claim_type == "pending" and claim.claim_id in edited
            ),
        )

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
        application_id: str,
        operation_id: str,
        draft: DraftDocument,
        knowledge: Knowledge,
        selected: list[str],
        writer_evidence: ProviderEvidence | None,
        *,
        claim_ids: set[str],
        model: str | None,
        reasoning_effort: str | None,
    ) -> tuple[DraftDocument, ProviderEvidence | None]:
        """Semantic review of the pending claims among `claim_ids` - only those.

        A pending line the Operation did not touch is not its to authorize or to fail on.
        """
        pending_ids = {
            claim.claim_id
            for claim in draft_claims(draft)
            if claim.claim_type == "pending" and claim.claim_id in claim_ids
        }
        if not pending_ids:
            return draft, None
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
        try:
            reviewed = self.provider.assess_claim_support(
                AssessClaimSupportContext(
                    language=draft.language,
                    claims=claims,
                    allowed_facts=fact_context(knowledge.facts, selected, draft.language),
                ),
                model=model,
                reasoning_effort=reasoning_effort,
            )
            evidence = self.preserve(
                application_id, operation_id, "assess_claim_support", reviewed.provenance
            )
            with evidence_attached(evidence):
                authorized = authorize_semantically_reviewed_claims(
                    draft, reviewed.proposal, knowledge.facts, evidence, claim_ids=pending_ids
                )
        except ApplicationError as exc:
            if writer_evidence is not None:
                exc.completed_evidence = (writer_evidence,)
            raise
        return authorized, evidence

    def prepare_section_regeneration(
        self, command: RegenerateSectionCommand, *, operation_id: str
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
        answered = self.provider.regenerate_section(
            RegenerateSectionContext(
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
            ),
            model=command.model,
            reasoning_effort=command.reasoning_effort,
        )
        evidence = self.preserve(
            command.application_id, operation_id, "regenerate_section", answered.provenance
        )
        proposed = answered.proposal
        with evidence_attached(evidence):
            if proposed.section != section.name:
                raise ProposalRejected(
                    f"regenerate_section answered for section {proposed.section!r}, not {section.name!r}"
                )
            updated = apply_proposed_claims(
                draft,
                proposed.claims,
                knowledge.facts,
                set(allowed),
                task="regenerate_section",
                allow_semantic_review=True,
            )
        updated, review_evidence = self._review_pending_claims(
            command.application_id,
            operation_id,
            updated,
            knowledge,
            allowed,
            evidence,
            claim_ids=_changed_claim_ids(draft, updated),
            model=command.model,
            reasoning_effort=command.reasoning_effort,
        )
        return PreparedRegeneration(
            application_id=command.application_id,
            expected_document_hash=command.expected_document_hash,
            content=updated,
            claim_ids=[str(claim.claim_id) for claim in proposed.claims],
            evidence=evidence,
            review_evidence=review_evidence,
        )

    def prepare_claim_regeneration(
        self, command: RegenerateClaimCommand, *, operation_id: str
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
            # nothing on its own - `authorize_semantically_reviewed_claims` applies the
            # same hard checks it applies to writer output.
            if claim.claim_type != "pending" or not claim.fact_ids:
                raise ProposalRejected(
                    "only a pending claim linked to at least one fact can have its own wording reviewed"
                )
            reviewed, review_evidence = self._review_pending_claims(
                command.application_id,
                operation_id,
                draft,
                knowledge,
                allowed,
                None,
                claim_ids={claim.claim_id},
                model=command.model,
                reasoning_effort=command.reasoning_effort,
            )
            if review_evidence is None:
                raise ProposalRejected("semantic review produced no evidence")
            return PreparedRegeneration(
                application_id=command.application_id,
                expected_document_hash=command.expected_document_hash,
                content=reviewed,
                claim_ids=[claim.claim_id],
                evidence=review_evidence,
            )
        answered = self.provider.regenerate_claim(
            RegenerateClaimContext(
                claim_id=claim.claim_id,
                section=section.name,
                language=draft.language,
                job_analysis=self._analysis_context(analysis),
                current_text=claim.text,
                allowed_facts=fact_context(knowledge.facts, allowed, draft.language),
                instruction=command.instruction,
            ),
            model=command.model,
            reasoning_effort=command.reasoning_effort,
        )
        evidence = self.preserve(
            command.application_id, operation_id, "regenerate_claim", answered.provenance
        )
        proposed = answered.proposal
        with evidence_attached(evidence):
            if proposed.claim_id != claim.claim_id:
                raise ProposalRejected(
                    f"regenerate_claim answered for claim {proposed.claim_id!r}, not {claim.claim_id!r}"
                )
            updated = apply_proposed_claims(
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
                allow_semantic_review=True,
            )
        updated, review_evidence = self._review_pending_claims(
            command.application_id,
            operation_id,
            updated,
            knowledge,
            allowed,
            evidence,
            claim_ids=_changed_claim_ids(draft, updated),
            model=command.model,
            reasoning_effort=command.reasoning_effort,
        )
        return PreparedRegeneration(
            application_id=command.application_id,
            expected_document_hash=command.expected_document_hash,
            content=updated,
            claim_ids=[proposed.claim_id],
            evidence=evidence,
            review_evidence=review_evidence,
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
