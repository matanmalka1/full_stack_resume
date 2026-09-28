"""The CV document's basis and the states derived from it (state-and-use-cases.md §3–§5).

Everything here is computed on read. `document_hash` is the one value that is also
stored, because commands compare it as the document's concurrency token; the basis
and every state are derived from the stored document and the Knowledge loaded with it,
so a change to either is visible on the next read without any write.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from enum import StrEnum

from ..util import canonical_json, sha256_text
from .contracts.document import CVDocument
from .contracts.drafts import DraftDocument
from .contracts.knowledge import Fact
from .contracts.selection import SelectionManifest


class PreparationState(StrEnum):
    NEEDS_ANALYSIS = "needs_analysis"
    READY_TO_DRAFT = "ready_to_draft"
    DRAFT_IN_PROGRESS = "draft_in_progress"
    APPROVED = "approved"
    READY = "ready"


class DocumentState(StrEnum):
    NONE = "none"
    DRAFT = "draft"
    APPROVED = "approved"
    READY = "ready"


class ContentCheck(StrEnum):
    NONE = "none"
    OUTDATED = "outdated"
    FAILED = "failed"
    PASSED = "passed"


def document_hash(
    analysis_id: str, selection: SelectionManifest, content: DraftDocument | None
) -> str:
    return sha256_text(
        canonical_json(
            {
                "analysis_id": analysis_id,
                "selection": selection.model_dump(mode="json"),
                "content": None if content is None else content.model_dump(mode="json"),
            }
        )
    )


def dependent_fact_ids(
    selection: SelectionManifest, content: DraftDocument | None
) -> frozenset[str]:
    """The facts the document depends on: its selection united with its claims' facts.

    The same set decides `facts_hash` and the fact review reasons (§7), so a fact can
    never block a document without also being able to change its basis.
    """
    fact_ids = set(selection.selected_fact_ids) | set(selection.pinned_fact_ids)
    if content is not None:
        claims = [
            content.headline,
            *content.contacts,
            *(claim for section in content.sections for claim in section.claims),
        ]
        fact_ids.update(fact_id for claim in claims for fact_id in claim.fact_ids)
    return frozenset(fact_ids)


def facts_hash(fact_ids: Iterable[str], facts: Mapping[str, Fact]) -> str:
    """Hash the current state of every named fact, including its lifecycle status.

    Where the fact is stored (`source_file`) is not part of it; everything the fact
    says is. A fact that no longer resolves is entered as missing rather than skipped,
    so losing a fact changes the hash.
    """
    entries = []
    for fact_id in sorted(set(fact_ids)):
        fact = facts.get(fact_id)
        if fact is None:
            entries.append({"fact_id": fact_id, "missing": True})
        else:
            entries.append(fact.model_dump(mode="json", exclude={"source_file"}))
    return sha256_text(canonical_json(entries))


def basis(document: CVDocument, facts: Mapping[str, Fact]) -> str:
    dependent = dependent_fact_ids(document.selection, document.content)
    return sha256_text(f"{document.document_hash}:{facts_hash(dependent, facts)}")


def document_state(document: CVDocument | None, current_basis: str | None) -> DocumentState:
    if document is None:
        return DocumentState.NONE
    if document.approved_basis is None or document.approved_basis != current_basis:
        return DocumentState.DRAFT
    if document.rendered_basis == current_basis:
        return DocumentState.READY
    return DocumentState.APPROVED


def content_check(document: CVDocument | None, current_basis: str | None) -> ContentCheck:
    if document is None or document.content is None or document.checked_basis is None:
        return ContentCheck.NONE
    if document.checked_basis != current_basis:
        return ContentCheck.OUTDATED
    return ContentCheck.PASSED if document.passed else ContentCheck.FAILED


def preparation_state(document: CVDocument | None, current_basis: str | None) -> PreparationState:
    if document is None:
        return PreparationState.NEEDS_ANALYSIS
    if document.content is None:
        return PreparationState.READY_TO_DRAFT
    state = document_state(document, current_basis)
    if state is DocumentState.READY:
        return PreparationState.READY
    if state is DocumentState.APPROVED:
        return PreparationState.APPROVED
    return PreparationState.DRAFT_IN_PROGRESS
