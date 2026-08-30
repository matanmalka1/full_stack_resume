"""§14: provider wording for one section or one claim, over a frozen version."""

from __future__ import annotations

from dataclasses import dataclass

from ....domain.knowledge import Knowledge
from ....domain.models import DraftDocument, JobAnalysis, ProposedClaim, WorkingDraft
from ...commands import RegenerateClaimCommand, RegenerateSectionCommand, RegenerationResult
from ...errors import (
    # Re-exported: the API and test suite catch WorkflowError from here, and
    # it is bound to the taxonomy's base class, so every refusal below is caught.
    LineageBroken,
    ProposalRejected,
    StateConflict,
    UnknownRecord,
)
from ...ports import DraftRepository, RegenerateClaimContext, RegenerateSectionContext
from ..proposals import (
    ProviderEvidence,
    apply_proposed_claims,
    evidence_attached,
    fact_context,
)
from .common import DraftServiceBase


@dataclass(frozen=True)
class PreparedRegeneration:
    """One accepted regeneration, computed but not yet committed.

    The document already carries the proposed wording: it passed
    `apply_proposed_claims`, which is the same authority a manual edit passes,
    so anything unsupported was refused before this value could exist. What is
    left is the optimistic commit against the exact version that was frozen.
    """

    working: WorkingDraft
    source: DraftDocument
    claim_ids: list[str]
    evidence: ProviderEvidence


class DraftRegeneration(DraftServiceBase):
    """Replacement wording, proposed against an exact version and committed against it."""

    def _regeneration_target(
        self,
        application_id: str,
        working_draft_id: str,
        expected_edit_version: int,
        expected_content_hash: str,
        job_analysis_id: str,
        selection_plan_id: str,
    ) -> tuple[WorkingDraft, Knowledge, JobAnalysis]:
        """The exact draft version a regeneration named, or the refusal that says why.

        All three parts of the draft's identity are checked, plus the analysis
        and plan the client stated. §14 requires regeneration to receive exact
        WorkingDraft ID, version, and hash - so a regeneration launched against
        one version and activated against another is a `409`, not a silent
        overwrite of whatever the draft became in between.
        """
        working = self._working(working_draft_id, expected_edit_version)
        if working.application_id != application_id:
            raise LineageBroken(
                f"working draft {working.id} does not belong to application {application_id}"
            )
        if working.content_hash != expected_content_hash:
            raise StateConflict(
                f"working draft {working.id} has content hash {working.content_hash}, "
                f"not {expected_content_hash}"
            )
        if working.job_analysis_id != job_analysis_id:
            raise LineageBroken(
                f"working draft {working.id} was built from analysis "
                f"{working.job_analysis_id}, not {job_analysis_id}"
            )
        if working.selection_plan_id != selection_plan_id:
            raise LineageBroken(
                f"working draft {working.id} was built from selection plan "
                f"{working.selection_plan_id}, not {selection_plan_id}"
            )
        knowledge = self.load_knowledge()
        record = self.repo.get_analysis(working.job_analysis_id)
        return working, knowledge, record["analysis"]

    def prepare_section_regeneration(
        self,
        command: RegenerateSectionCommand,
        *,
        operation_id: str,
    ) -> PreparedRegeneration:
        """§14 `regenerate_section`: propose replacement wording for one section."""
        working, knowledge, analysis = self._regeneration_target(
            command.application_id,
            command.working_draft_id,
            command.expected_edit_version,
            command.expected_content_hash,
            command.job_analysis_id,
            command.selection_plan_id,
        )
        draft = working.source
        section = next(
            (item for item in draft.sections if item.name == command.section),
            None,
        )
        if section is None:
            raise UnknownRecord(f"unknown section in the working draft: {command.section}")
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
            )
        )
        evidence = self.preserve(
            command.application_id, operation_id, "regenerate_section", answered.provenance
        )
        proposed = answered.proposal
        with evidence_attached(evidence):
            if proposed.section != section.name:
                raise ProposalRejected(
                    f"regenerate_section answered for section {proposed.section!r}, "
                    f"not {section.name!r}"
                )
            updated = apply_proposed_claims(
                draft,
                proposed.claims,
                knowledge.facts,
                set(allowed),
                task="regenerate_section",
            )
        return PreparedRegeneration(
            working=working,
            source=updated,
            claim_ids=[str(claim.claim_id) for claim in proposed.claims],
            evidence=evidence,
        )

    def prepare_claim_regeneration(
        self,
        command: RegenerateClaimCommand,
        *,
        operation_id: str,
    ) -> PreparedRegeneration:
        """§14 `regenerate_claim`: propose replacement wording for one claim."""
        working, knowledge, analysis = self._regeneration_target(
            command.application_id,
            command.working_draft_id,
            command.expected_edit_version,
            command.expected_content_hash,
            command.job_analysis_id,
            command.selection_plan_id,
        )
        draft = working.source
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
            raise UnknownRecord(f"unknown claim in the working draft: {command.claim_id}")
        section, claim = located
        allowed = sorted(claim.fact_ids)
        answered = self.provider.regenerate_claim(
            RegenerateClaimContext(
                claim_id=claim.claim_id,
                section=section.name,
                language=draft.language,
                job_analysis=self._analysis_context(analysis),
                current_text=claim.text,
                allowed_facts=fact_context(knowledge.facts, allowed, draft.language),
                instruction=command.instruction,
            )
        )
        evidence = self.preserve(
            command.application_id, operation_id, "regenerate_claim", answered.provenance
        )
        proposed = answered.proposal
        with evidence_attached(evidence):
            if proposed.claim_id != claim.claim_id:
                raise ProposalRejected(
                    f"regenerate_claim answered for claim {proposed.claim_id!r}, "
                    f"not {claim.claim_id!r}"
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
            )
        return PreparedRegeneration(
            working=working,
            source=updated,
            claim_ids=[proposed.claim_id],
            evidence=evidence,
        )

    @staticmethod
    def _analysis_context(analysis: JobAnalysis) -> dict:
        """The narrow analysis view a wording task needs.

        Not the analysis record. Requirements, Fit, approval routing, and
        overrides decide policy, and a task that does not receive them cannot
        be argued into changing them by the job text it is given.
        """
        return {
            "track": analysis.track.value,
            "profile": analysis.profile.value,
            "emphasis": analysis.emphasis.value,
            "language": analysis.language,
            "keywords": list(analysis.keywords),
        }

    def activate_regeneration(
        self,
        prepared: PreparedRegeneration,
        repository: DraftRepository | None = None,
    ) -> RegenerationResult:
        """Commit regenerated wording against the exact version that was frozen.

        The update carries `expected_edit_version`, so a save that happened
        while the Operation ran makes this commit fail rather than overwrite it.
        The provider evidence is registered in the same transaction as the
        wording it produced.
        """
        repo = repository or self.repo
        working = prepared.working
        changed = repo.update_working_draft(
            working.id,
            working.edit_version,
            prepared.source,
        )
        self.store_working_draft(changed.source)
        return RegenerationResult(
            application_id=changed.application_id,
            working_draft_id=changed.id,
            edit_version=changed.edit_version,
            content_hash=changed.content_hash,
            selection_plan_id=changed.selection_plan_id,
            regenerated_claim_ids=list(prepared.claim_ids),
            provider_artifact_version_id=prepared.evidence.artifact_version_id,
        )
