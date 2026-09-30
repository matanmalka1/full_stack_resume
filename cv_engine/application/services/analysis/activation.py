"""Analysis and selection-proposal activation in a caller-owned transaction.

No external effects happen here: every provider call and file read is finished
before these run, inside the Operation runner's activation scope or a service's
own write scope.
"""

from __future__ import annotations

from ....domain.knowledge import Knowledge
from ....util import utc_now
from ...commands import AnalysisResult, AnalyzeCommand, ProposeSelectionCommand
from ...errors import LineageBroken, PreconditionFailed
from ...ports.analysis_plans import AnalysisSelectionSourceReader, AnalysisStore
from ...ports.documents import DocumentBody, DocumentStore
from ...ports.transactions import WriteTransaction
from ..documents import (
    changed_selection,
    lock_document_source,
    refuse_deleted,
    require_hash,
)
from .preparation import PreparedAnalysis
from .selection_policy import PreparedSelectionProposal


class AnalysisActivation:
    def __init__(
        self,
        analyses: AnalysisStore,
        sources: AnalysisSelectionSourceReader,
        documents: DocumentStore,
    ):
        self.analyses = analyses
        self.sources = sources
        self.documents = documents

    def activate(
        self, tx: WriteTransaction, command: AnalyzeCommand, prepared: PreparedAnalysis
    ) -> AnalysisResult:
        """Write one immutable JobAnalysis; create the document if there is none (§13).

        A later analysis never changes an existing document: it raises the
        `DOCUMENT_ON_OLDER_ANALYSIS` warning on the next read, and only
        `build_from_analysis` re-pins. Creation relies on the one-document-per-
        Application unique constraint, under the Application lock taken first.
        """
        # The runner takes this lock as its first statement; direct callers get the
        # same ordering here before reading any source or allocating any version.
        self.analyses.lock_application(tx, command.application_id)
        source = self.sources.analysis_source(tx, command.job_snapshot_id)
        if source.application_id != command.application_id:
            raise LineageBroken("job snapshot does not belong to the named Application")
        refuse_deleted(command.application_id, source.deleted_at)
        document = self.documents.lock_document(tx, command.application_id)
        if document is not None and command.expected_analysis_id is not None:
            # A decision against an existing context names the document it was made
            # beside; the analysis it creates leaves that document untouched.
            if command.expected_document_hash is None:
                raise PreconditionFailed(
                    "a decision made beside a CV document must name it (expected_document_hash)"
                )
            require_hash(document, command.expected_document_hash)
        analysis_id = self.analyses.save_analysis(
            tx,
            command.application_id,
            command.job_snapshot_id,
            prepared.result,
            provider=prepared.provider,
            model=prepared.model,
            expected_analysis_id=command.expected_analysis_id,
            refuse_matching_context_operation=command.refuse_matching_context_operation,
        )
        self.analyses.set_normalized_role(tx, command.application_id, prepared.normalized_role)
        created = False
        if document is None:
            document = self.documents.create_document(
                tx,
                command.application_id,
                DocumentBody(analysis_id=analysis_id, selection=prepared.selection, content=None),
                prepared.built_with,
                created_at=utc_now(),
            )
            created = True
        return AnalysisResult(
            application_id=command.application_id,
            job_snapshot_id=command.job_snapshot_id,
            analysis_id=analysis_id,
            document_id=document.id,
            created_document=created,
            analysis=prepared.result,
        )

    def activate_selection_proposal(
        self,
        tx: WriteTransaction,
        command: ProposeSelectionCommand,
        prepared: PreparedSelectionProposal,
        knowledge: Knowledge,
    ) -> str:
        """Replace the selection with an AI proposal, after repeating every check (§14).

        The expected hash is re-checked under the row lock, and the overlay is run
        through selection policy again against the Knowledge loaded for activation.
        The provider's proposal is never trusted on its own. The write follows
        `update_selection`'s content rule: content nobody has worded is dropped, to be
        drafted again, and authored wording refuses the activation. Rendered files it
        releases are left to orphan maintenance.
        """
        source = lock_document_source(tx, self.documents, self.sources, command.application_id)
        refuse_deleted(command.application_id, source.deleted_at)
        require_hash(source.document, command.expected_document_hash)
        selection = changed_selection(
            source,
            knowledge,
            pinned_fact_ids=prepared.proposal.pinned_fact_ids,
            excluded_fact_ids=prepared.proposal.excluded_fact_ids,
            emphasis_override=None,
            ai_rationale=prepared.proposal.rationale,
        )
        updated, _released = self.documents.replace_selection(
            tx,
            command.application_id,
            command.expected_document_hash,
            selection,
            updated_at=utc_now(),
        )
        return updated.id
