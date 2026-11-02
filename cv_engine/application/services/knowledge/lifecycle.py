"""The fact lifecycle: the commands that move a fact. The reads over it are `queries`.

Knowledge is the user's rows in PostgreSQL (architecture §18.2), so a fact mutation is
one database transaction. It reads the rows, applies the change to them in memory,
builds the whole Knowledge they would make - which validates every fact, Profile and
the candidate context as loading always has - and only then writes the rows that
changed, advances the user's `fact_store_version`, and appends the fact events. A
proposal that does not build is refused and nothing is written.

The cross-store journal this replaced (§7.2) is retired, and its table is dropped.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any

from ....domain.contracts.knowledge import Fact, FactStatus
from ....domain.facts import FactStore, FactStoreError, build_new_fact, source_id_of_name
from ....domain.knowledge import Knowledge
from ....domain.knowledge_import import fact_from_row, fact_row, split_profile
from ....domain.profiles import attach_fact_to_section
from ....util import new_id, utc_now
from ...actor import Actor
from ...commands import ConfirmAndUseFactResult, FactAttachmentResult, FactMutationResult
from ...errors import InfrastructureFailure, KnowledgeRejected, UnknownRecord
from ...ports.analysis_plans import AnalysisContextSourceReader
from ...ports.documents import DocumentStore
from ...ports.knowledge_lifecycle import KnowledgeLifecycleStore
from ...ports.transactions import ReadTransaction, TransactionManager, WriteTransaction
from ...ports.user_knowledge import StoredKnowledge, UserKnowledgeRepository, UserKnowledgeSource

__all__ = ["FactLifecycleService"]


def _transition(store: FactStore, fact_id: str, change: Callable[[str], Fact]) -> tuple[Fact, Fact]:
    """The fact before and after `change`, with the store's refusals mapped."""
    try:
        return store.get(fact_id), change(fact_id)
    except FactStoreError as exc:
        if fact_id not in store.facts:
            raise UnknownRecord(f"Unknown fact: {fact_id}") from exc
        raise KnowledgeRejected(str(exc)) from exc
    except ValueError as exc:
        raise KnowledgeRejected(str(exc)) from exc


def _with_fact(state: StoredKnowledge, fact: Fact) -> StoredKnowledge:
    """`state` with one existing fact's row replaced, in place."""
    return replace(
        state,
        facts=[
            fact_row(fact, row["source"], row["ordinal"]) if row["fact_id"] == fact.fact_id else row
            for row in state.facts
        ],
    )


class FactLifecycleService:
    """The fact lifecycle and the knowledge version surface."""

    def __init__(
        self,
        *,
        transactions: TransactionManager,
        store: KnowledgeLifecycleStore,
        knowledge: UserKnowledgeSource,
        repository: UserKnowledgeRepository,
        documents: DocumentStore,
        sources: AnalysisContextSourceReader,
    ) -> None:
        self.transactions = transactions
        self.store = store
        self._knowledge = knowledge
        self._repo = repository
        self.documents = documents
        self._sources = sources

    # The one write path.

    def _build(self, state: StoredKnowledge) -> Knowledge:
        try:
            return self._knowledge.build(state)
        except OSError as exc:
            raise InfrastructureFailure(f"could not read Knowledge policy: {exc}") from exc
        except ValueError as exc:
            raise KnowledgeRejected(str(exc)) from exc

    def _state(self, tx: ReadTransaction, actor: Actor) -> StoredKnowledge:
        try:
            return self._knowledge.state(tx, actor.user_id)
        except ValueError as exc:
            raise KnowledgeRejected(str(exc)) from exc

    def _commit(
        self,
        tx: WriteTransaction,
        current: StoredKnowledge,
        proposed: StoredKnowledge,
        events: list[dict[str, Any]],
    ) -> tuple[Knowledge, list[str]]:
        """Validate `proposed` as a whole, write what differs from `current`, record events."""
        knowledge = self._build(proposed)
        now = utc_now()
        # The optimistic check that serializes two mutations of the same Knowledge, made
        # first: a write from a stale read is refused before it touches a row, rather
        # than failing later on whichever unique key the two writes happen to share.
        self._repo.advance_fact_store_version(
            tx, current.user_id, expected=current.fact_store_version, now=now
        )
        before = {row["fact_id"]: row for row in current.facts}
        for row in proposed.facts:
            stored = before.get(row["fact_id"])
            if stored is None:
                self._repo.insert_fact(tx, current.user_id, row, now=now)
            elif stored != row:
                self._repo.update_fact(tx, current.user_id, row, now=now)
        for profile_id, binding in proposed.bindings.items():
            if binding != current.bindings.get(profile_id):
                self._repo.set_binding(
                    tx,
                    current.user_id,
                    profile_id,
                    binding,
                    expected_version=current.binding_versions[profile_id],
                    now=now,
                )
        event_ids = []
        for event in events:
            event_ids.append(
                self.store.record_fact_event(
                    tx,
                    **event,
                    user_id=current.user_id,
                    facts_version=knowledge.facts.version,
                    lifecycle_version=knowledge.facts.lifecycle_version,
                    created_at=now,
                )
            )
        return knowledge, event_ids

    @staticmethod
    def _event(
        fact: Fact,
        *,
        event_type: str,
        from_status: str | None,
        reason: str,
        application_id: str | None = None,
        claim_id: str | None = None,
    ) -> dict[str, Any]:
        return {
            "event_id": new_id(),
            "fact_id": fact.fact_id,
            "source_file": fact.source_file,
            "event_type": event_type,
            "from_status": from_status,
            "to_status": fact.status.value,
            "fact": fact.model_dump(mode="json"),
            "reason": reason,
            "application_id": application_id,
            "claim_id": claim_id,
        }

    @staticmethod
    def _result(fact: Fact, knowledge: Knowledge, event_ids: list[str]) -> FactMutationResult:
        return FactMutationResult(
            fact=fact,
            event_id=event_ids[0],
            facts_version=knowledge.facts.version,
            lifecycle_version=knowledge.facts.lifecycle_version,
        )

    # Commands.

    def add_fact(
        self,
        actor: Actor,
        source: str,
        payload: dict[str, Any],
        *,
        reason: str = "",
        application_id: str | None = None,
        claim_id: str | None = None,
    ) -> FactMutationResult:
        """Create a new `pending` fact in its source and record the event.

        A pending fact cannot reach a CV: every rendering path resolves facts with
        `canonical_only=True`; it becomes canonical only through `confirm_fact`.
        """
        with self.transactions.write() as tx:
            if application_id is not None:
                # The Application a new fact is recorded beside is the user's own.
                self._sources.require_owned(tx, application_id, actor.user_id)
            return self.add_fact_in(
                tx,
                actor,
                source,
                payload,
                reason=reason,
                application_id=application_id,
                claim_id=claim_id,
            )

    def add_fact_in(
        self,
        tx: WriteTransaction,
        actor: Actor,
        source: str,
        payload: dict[str, Any],
        *,
        reason: str = "",
        application_id: str | None = None,
        claim_id: str | None = None,
    ) -> FactMutationResult:
        """`add_fact` inside a scope the caller owns: an Operation's activation.

        A gap answer's fact (§17) is written in the same transaction as the record
        that the question was answered, so one never exists without the other. The
        caller has already resolved `application_id` for `actor`.
        """
        current = self._state(tx, actor)
        store = self._build(current).facts
        try:
            record = build_new_fact(store, source, payload, canonical=False)
        except (FactStoreError, ValueError) as exc:
            raise KnowledgeRejected(str(exc)) from exc
        source_id = source_id_of_name(source)
        ordinal = 1 + max(
            (row["ordinal"] for row in current.facts if row["source"] == source_id),
            default=0,
        )
        row = fact_row(record, source_id, ordinal)
        fact = fact_from_row(row)
        knowledge, event_ids = self._commit(
            tx,
            current,
            replace(current, facts=[*current.facts, row]),
            [
                self._event(
                    fact,
                    event_type="fact_created",
                    from_status=None,
                    reason=reason or "new pending fact",
                    application_id=application_id,
                    claim_id=claim_id,
                )
            ],
        )
        return self._result(fact, knowledge, event_ids)

    def create_pending_fact(
        self,
        actor: Actor,
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
            actor,
            source,
            {**payload, "fact_id": new_id()},
            reason=reason,
            application_id=application_id,
            claim_id=claim_id,
        )

    @staticmethod
    def _confirmed(store: FactStore, fact_id: str) -> tuple[Fact, Fact]:
        """§17: `pending -> canonical`; the date of confirmation unless one is recorded."""
        before, confirmed = _transition(
            store, fact_id, lambda fid: store.confirm(fid, explicitly_confirmed=True)
        )
        return before, confirmed.model_copy(
            update={"confirmed_at": before.confirmed_at or utc_now()[:10]}
        )

    def confirm_fact(
        self,
        actor: Actor,
        fact_id: str,
        *,
        explicitly_confirmed: bool,
        reason: str = "",
    ) -> FactMutationResult:
        """§17: `pending -> canonical` on one explicit attestation."""
        if not explicitly_confirmed:
            raise KnowledgeRejected("fact confirmation requires explicit confirmation")
        with self.transactions.write() as tx:
            current = self._state(tx, actor)
            before, after = self._confirmed(self._build(current).facts, fact_id)
            knowledge, event_ids = self._commit(
                tx,
                current,
                _with_fact(current, after),
                [
                    self._event(
                        after,
                        event_type="fact_confirmed",
                        from_status=before.status.value,
                        reason=reason or "explicit confirmation",
                    )
                ],
            )
        return self._result(after, knowledge, event_ids)

    def delete_fact(
        self,
        actor: Actor,
        fact_id: str,
        *,
        explicitly_confirmed: bool,
        reason: str = "",
    ) -> FactMutationResult:
        """One-way transition to `deleted`.

        Always permitted regardless of Profile attachment or a document that depends
        on the fact. It writes nothing to any document: the document's basis changes,
        and the `FACT_DELETED_REQUIRES_RESOLUTION` review reason reports the
        consequence rather than this command refusing it (§17).
        """
        if not explicitly_confirmed:
            raise KnowledgeRejected("fact deletion requires explicit confirmation")
        with self.transactions.write() as tx:
            current = self._state(tx, actor)
            store = self._build(current).facts
            before, after = _transition(store, fact_id, store.delete)
            knowledge, event_ids = self._commit(
                tx,
                current,
                _with_fact(current, after),
                [
                    self._event(
                        after,
                        event_type="fact_deleted",
                        from_status=before.status.value,
                        reason=reason or "explicit deletion",
                    )
                ],
            )
        return self._result(after, knowledge, event_ids)

    def edit_pending_fact(
        self,
        actor: Actor,
        fact_id: str,
        *,
        meaning: str | None = None,
        renderings: dict[str, str] | None = None,
        tags: list[str] | None = None,
        effective_dates: str | None = None,
        reason: str = "",
    ) -> FactMutationResult:
        """§17: change what a pending fact says, in place, before it is confirmed.

        Only a `pending` fact: it reaches no CV until confirmed, so its wording is
        still the user's to settle (a gap answer's draft is reviewed this way). A
        canonical fact is corrected by a replacement, and a deleted one not at all.
        Identity, source, style, provenance, and status do not change. Appends a
        `fact_edited` event carrying the fact as it now reads.
        """
        changes: dict[str, Any] = {
            name: value
            for name, value in (
                ("meaning", meaning),
                ("renderings", renderings),
                ("tags", tags),
                ("effective_dates", effective_dates),
            )
            if value is not None
        }
        if not changes:
            raise KnowledgeRejected("an edit must change at least one field")
        with self.transactions.write() as tx:
            current = self._state(tx, actor)
            store = self._build(current).facts
            try:
                before = store.get(fact_id)
            except FactStoreError as exc:
                raise UnknownRecord(f"Unknown fact: {fact_id}") from exc
            if before.status is not FactStatus.PENDING:
                raise KnowledgeRejected(
                    f"only a pending fact can be edited: {fact_id} ({before.status.value})"
                )
            try:
                after = Fact.model_validate({**before.model_dump(mode="json"), **changes})
            except ValueError as exc:
                raise KnowledgeRejected(str(exc)) from exc
            if after == before:
                raise KnowledgeRejected("the edit changes nothing")
            knowledge, event_ids = self._commit(
                tx,
                current,
                _with_fact(current, after),
                [
                    self._event(
                        after,
                        event_type="fact_edited",
                        from_status=before.status.value,
                        reason=reason or "edited before confirmation",
                    )
                ],
            )
        return self._result(after, knowledge, event_ids)

    def create_fact_from_claim(
        self,
        actor: Actor,
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
        """Turn an unsupported manual claim into a tracked fact.

        This is the product entry point into the lifecycle: a manual edit whose
        wording the fact store cannot support becomes a `pending` claim, and the
        claim's own text becomes the candidate fact rather than being retyped,
        so nothing is strengthened on the way in.
        """
        with self.transactions.read() as tx:
            self._sources.require_owned(tx, application_id, actor.user_id)
            document = self.documents.document(tx, application_id)
        if document is None or document.content is None:
            raise UnknownRecord(f"application {application_id} has no document content")
        draft = document.content
        claims = [
            draft.headline,
            *draft.contacts,
            *(claim for section in draft.sections for claim in section.claims),
        ]
        try:
            claim = next(item for item in claims if item.claim_id == claim_id)
        except StopIteration as exc:
            raise UnknownRecord(f"unknown claim in the document: {claim_id}") from exc
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
            actor,
            source,
            {
                "fact_id": new_id(),
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
            reason=reason or f"captured from claim {claim_id}",
            application_id=application_id,
            claim_id=claim_id,
        )

    @staticmethod
    def _attached(
        knowledge: Knowledge,
        current: StoredKnowledge,
        fact_id: str,
        profile: str,
        section: str,
        *,
        pin: bool,
    ) -> tuple[StoredKnowledge, Any, str]:
        """`current` with the fact offered to one Profile section's pool, and that Profile."""
        try:
            stored = knowledge.profiles.get(profile)
            origin = knowledge.profiles.source(profile)
            updated, _document = attach_fact_to_section(
                stored.model_dump(mode="json"), fact_id, section, origin=origin, pin=pin
            )
            _template, binding = split_profile(updated)
        except (KeyError, ValueError) as exc:
            raise KnowledgeRejected(str(exc)) from exc
        bindings = {**current.bindings, updated.profile_id: binding}
        return replace(current, bindings=bindings), updated, origin

    def attach_fact(
        self, actor: Actor, fact_id: str, profile: str, section: str, *, pin: bool = False
    ) -> FactAttachmentResult:
        """Offer a canonical fact to one Profile section's candidate pool."""
        with self.transactions.write() as tx:
            current = self._state(tx, actor)
            loaded = self._build(current)
            try:
                fact = loaded.facts.get(fact_id)
            except FactStoreError as exc:
                raise UnknownRecord(f"Unknown fact: {fact_id}") from exc
            if fact.status is not FactStatus.CANONICAL:
                raise KnowledgeRejected("only canonical facts may enter a Profile pool")
            proposed, updated, origin = self._attached(
                loaded, current, fact_id, profile, section, pin=pin
            )
            knowledge, event_ids = self._commit(
                tx,
                current,
                proposed,
                [
                    self._event(
                        fact,
                        event_type="fact_attached_to_profile",
                        from_status=fact.status.value,
                        reason=f"attached to {updated.profile.value} / {section}"
                        + (" (pinned)" if pin else ""),
                    )
                ],
            )
        record = self._result(fact, knowledge, event_ids)
        return FactAttachmentResult(
            **record.model_dump(),
            profile=updated.profile.value,
            section=section,
            pinned=pin,
            profile_source=origin,
            profile_store_version=knowledge.profiles.version,
        )

    def confirm_and_use_fact(
        self,
        actor: Actor,
        fact_id: str,
        *,
        application_id: str,
        job_analysis_id: str,
        profile: str,
        section: str,
        reason: str = "",
    ) -> ConfirmAndUseFactResult:
        """Confirm one pending fact and attach it to a Profile section, together (§17).

        The document must be built on the named analysis, whose Profile is `profile`.
        Nothing is written to the document: a claim already linking the fact stops
        raising the pending-fact review reason, and the next draft can choose it.
        """
        with self.transactions.write() as tx:
            self._sources.require_owned(tx, application_id, actor.user_id)
            document = self.documents.document(tx, application_id)
            # Another Application's analysis is `UnknownRecord` here.
            analysis_record = self.store.get_analysis(tx, job_analysis_id, application_id)
            if document is None:
                raise KnowledgeRejected(f"application {application_id} has no CV document yet")
            if document.analysis_id != job_analysis_id:
                raise KnowledgeRejected(
                    f"the document is built on analysis {document.analysis_id}, "
                    f"not {job_analysis_id}"
                )
            analysis = analysis_record["analysis"]
            if analysis.profile.value != profile:
                raise KnowledgeRejected(
                    f"analysis Profile {analysis.profile.value} does not match requested {profile}"
                )

            current = self._state(tx, actor)
            before, canonical = self._confirmed(self._build(current).facts, fact_id)
            confirmed = _with_fact(current, canonical)
            proposed, _updated, _origin = self._attached(
                self._build(confirmed), confirmed, fact_id, profile, section, pin=True
            )
            knowledge, event_ids = self._commit(
                tx,
                current,
                proposed,
                [
                    self._event(
                        canonical,
                        event_type="fact_confirmed",
                        from_status=before.status.value,
                        reason=reason or "explicit confirmation",
                        application_id=application_id,
                    ),
                    self._event(
                        canonical,
                        event_type="fact_attached_to_profile",
                        from_status=canonical.status.value,
                        reason=f"attached to {profile} / {section} (pinned)",
                        application_id=application_id,
                    ),
                ],
            )
        return ConfirmAndUseFactResult(
            fact=canonical,
            event_ids=event_ids,
            document_id=document.id,
            document_hash=document.document_hash,
            facts_version=knowledge.facts.version,
            lifecycle_version=knowledge.facts.lifecycle_version,
            profile_store_version=knowledge.profiles.version,
        )
