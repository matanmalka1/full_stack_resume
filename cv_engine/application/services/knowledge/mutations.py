"""The two-phase commit every Knowledge mutation runs through.

A fact mutation is not one write. It stages the Knowledge file on disk, records
a prepared mutation, activates the file, commits the database half, and only
then marks the journal entry committed and discards the staging directory. A
crash can land in any of those windows, so the engine is written to be resumed:
`recover_knowledge_mutations` re-runs `_complete_prepared` for every prepared
mutation at startup, and `_complete_prepared` decides from the recorded hashes
alone whether the mutation can still be finished, must be restored, or has to
be quarantined so no later command writes over an unresolved one.

Split out of `KnowledgeService` because it is the one part of this package that
is not regenerable: everything else here can be re-run, while a defect in the
recovery decision rewrites or strands a written record. It stays a base class
of the service rather than a collaborator it holds, because that is the shape
the recovery tests interrupt: they replace `_complete_prepared` on the service
instance to simulate a crash mid-mutation, and every internal caller reaches it
through `self`.
"""

from __future__ import annotations

from typing import Any

from ....domain.models import (
    Fact,
    SelectionManifest,
)
from ...commands import FactMutationResult
from ...errors import (
    # Re-exported: the CLI and test suite catch WorkflowError from here, and
    # it is bound to the taxonomy's base class, so every refusal below is caught.
    KnowledgeRejected,
    PreconditionFailed,
)
from ...knowledge_mutations import (
    KnowledgeMutation,
    PrepareKnowledgeMutation,
    StagedKnowledgeFile,
)
from ...ports import (
    KnowledgeAuditRepository,
)
from ..base import ServiceBase


class KnowledgeMutationEngine(ServiceBase[KnowledgeAuditRepository]):
    """Prepare, complete, restore, quarantine, and recover Knowledge mutations."""

    def _ensure_mutations_allowed(self) -> None:
        quarantined = self.repo.quarantined_knowledge_mutations()
        if quarantined:
            raise KnowledgeRejected(
                f"Knowledge mutations are quarantined by mutation {quarantined[0].id}"
            )

    @staticmethod
    def _apply_db_mutation(repository: KnowledgeAuditRepository, payload: dict[str, Any]) -> None:
        for action in payload.get("actions", []):
            if action.get("type") == "fact_event":
                repository.record_fact_event(
                    fact_id=action["fact_id"],
                    source_file=action["source_file"],
                    event_type=action["event_type"],
                    from_status=action["from_status"],
                    to_status=action["to_status"],
                    fact=action["fact"],
                    facts_version=action["facts_version"],
                    lifecycle_version=action["lifecycle_version"],
                    reason=action["reason"],
                    application_id=action["application_id"],
                    claim_id=action["claim_id"],
                    event_id=action["event_id"],
                    created_at=action["created_at"],
                )
            elif action.get("type") == "selection_plan":
                repository.create_selection_plan(
                    action["application_id"],
                    action["job_analysis_id"],
                    SelectionManifest.model_validate(action["plan"]),
                    candidate_context_version=action["candidate_context_version"],
                    candidate_context_hash=action["candidate_context_hash"],
                    profile_version=action["profile_version"],
                    selection_policy_version=action["selection_policy_version"],
                    track_emphasis_dependencies=action["track_emphasis_dependencies"],
                    plan_id=action["plan_id"],
                    created_at=action["created_at"],
                )
            else:
                raise ValueError(f"unknown Knowledge DB action: {action.get('type')}")

    def _quarantine(self, mutation: KnowledgeMutation, reason: str) -> None:
        try:
            self.repo.quarantine_knowledge_mutation(mutation.id, reason)
        except PreconditionFailed:
            pass

    def _staged_files(self, mutation: KnowledgeMutation) -> list[StagedKnowledgeFile]:
        files = [self._knowledge.staged_from_mutation(mutation)]
        for item in mutation.db_mutation.get("knowledge_files", []):
            files.append(
                StagedKnowledgeFile(
                    mutation_id=item["mutation_id"],
                    source_reference=item["source_reference"],
                    staged_reference=item["staged_reference"],
                    old_sha256=item["old_sha256"],
                    new_sha256=item["new_sha256"],
                    proposed_versions={},
                )
            )
        return files

    @staticmethod
    def _stored_staged_file(staged: StagedKnowledgeFile) -> dict[str, str]:
        return {
            "mutation_id": staged.mutation_id,
            "source_reference": staged.source_reference,
            "staged_reference": staged.staged_reference,
            "old_sha256": staged.old_sha256,
            "new_sha256": staged.new_sha256,
        }

    def _complete_prepared(self, mutation: KnowledgeMutation) -> None:
        staged_files = self._staged_files(mutation)
        states = [self._knowledge.staged_file_state(staged) for staged in staged_files]
        invalid = [
            (staged, state)
            for staged, state in zip(staged_files, states, strict=True)
            if state.backup_sha256 != staged.old_sha256
            or not (
                (
                    state.current_sha256 == staged.old_sha256
                    and state.staged_sha256 == staged.new_sha256
                )
                or (state.current_sha256 == staged.new_sha256 and state.staged_sha256 is None)
            )
        ]
        if invalid:
            for staged, state in zip(staged_files, states, strict=True):
                if (
                    state.current_sha256 == staged.new_sha256
                    and state.backup_sha256 == staged.old_sha256
                ):
                    self._knowledge.restore_staged(staged)
            reason = "Knowledge mutation files do not match the prepared old/new hashes"
            self._quarantine(mutation, reason)
            raise KnowledgeRejected(reason)
        for staged, state in zip(staged_files, states, strict=True):
            if state.current_sha256 == staged.old_sha256:
                self._knowledge.activate_staged(staged)

        try:
            with self.repo.unit_of_work() as uow:
                transaction = self.repo.bind(uow)
                self._apply_db_mutation(transaction, mutation.db_mutation)
                uow.commit()
        except Exception as exc:
            for staged in staged_files:
                state = self._knowledge.staged_file_state(staged)
                if (
                    state.current_sha256 == staged.new_sha256
                    and state.backup_sha256 == staged.old_sha256
                ):
                    self._knowledge.restore_staged(staged)
            reason = f"Knowledge DB mutation could not commit: {type(exc).__name__}: {exc}"
            self._quarantine(mutation, reason)
            raise KnowledgeRejected(reason) from exc

        self.repo.commit_knowledge_mutation(mutation.id)
        for staged in staged_files:
            try:
                self._knowledge.discard_staged(staged)
            except OSError:
                # The committed record and final source are authoritative. A leftover
                # temp directory is a safe reconciliation orphan, not a partial mutation.
                pass

    def recover_knowledge_mutations(self) -> list[str]:
        recovered: list[str] = []
        for mutation in self.repo.prepared_knowledge_mutations():
            try:
                self._complete_prepared(mutation)
            except KnowledgeRejected:
                continue
            recovered.append(mutation.id)
        return recovered

    def _run_fact_mutation(
        self,
        staged: StagedKnowledgeFile,
        fact: Fact,
        action: dict[str, Any],
    ) -> FactMutationResult:
        request = PrepareKnowledgeMutation(
            mutation_id=staged.mutation_id,
            mutation_type=action["event_type"],
            source_reference=staged.source_reference,
            staged_reference=staged.staged_reference,
            old_sha256=staged.old_sha256,
            new_sha256=staged.new_sha256,
            db_mutation_type="fact_event",
            db_mutation_id=action["event_id"],
            db_mutation={"actions": [action]},
            recovery_strategy="finish_or_restore",
        )
        try:
            mutation = self.repo.prepare_knowledge_mutation(request)
        except Exception:
            self._knowledge.discard_staged(staged)
            raise
        self._complete_prepared(mutation)
        return FactMutationResult(
            fact=fact,
            event_id=action["event_id"],
            facts_version=action["facts_version"],
            lifecycle_version=action["lifecycle_version"],
        )
