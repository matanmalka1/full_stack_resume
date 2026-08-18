from __future__ import annotations

import json
from pathlib import Path

from ..domain.candidate import CANDIDATE_FILE, CandidateContextError, build_candidate_context
from ..domain.facts import (
    FACT_SOURCE_NAMES,
    FactStore,
    FactStoreError,
    build_new_fact,
    parse_fact_source,
    parse_fact_source_document,
    render_fact_source,
    source_name_of,
    with_new_fact,
    with_promoted_fact,
)
from ..domain.knowledge import Knowledge
from ..domain.models import CandidateContext, Fact, FactSource, FactStatus, Profile
from ..domain.presentations import PresentationError, PresentationStore
from ..domain.profiles import ProfileStore, ProfileStoreError, attach_fact_to_section
from ..domain.selection import EmphasisPolicyStore, SelectionError
from ..util import utc_now


def read_fact_source(path: Path) -> FactSource:
    """One canonical fact source, parsed from its file."""
    return parse_fact_source(path.read_text(encoding="utf-8"), origin=str(path))


def write_fact_source(path: Path, title: str, source: FactSource) -> None:
    path.write_text(render_fact_source(title, source), encoding="utf-8")


def load_fact_store(base_dir: Path) -> FactStore:
    missing = [name for name in FACT_SOURCE_NAMES if not (base_dir / name).is_file()]
    if missing:
        raise FactStoreError(f"missing canonical fact sources: {', '.join(missing)}")
    return FactStore.from_sources(
        {name: read_fact_source(base_dir / name) for name in FACT_SOURCE_NAMES}
    )


def load_profile_store(knowledge_root: Path, facts: FactStore) -> ProfileStore:
    documents: dict[str, dict] = {}
    for path in sorted((knowledge_root / "profiles").glob("**/*.yaml")):
        try:
            documents[str(path)] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ProfileStoreError(f"invalid profile {path}: {exc}") from exc
    return ProfileStore.from_documents(documents, facts)


def load_emphasis_policies(knowledge_root: Path) -> EmphasisPolicyStore:
    path = knowledge_root / "config" / "emphasis.json"
    if not path.is_file():
        raise SelectionError(f"missing emphasis policy: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SelectionError(f"invalid emphasis policy {path}: {exc}") from exc
    return EmphasisPolicyStore.from_payload(payload, origin=str(path))


def load_presentations(knowledge_root: Path, facts: FactStore) -> PresentationStore:
    path = knowledge_root / "rendering" / "rules" / "presentations.json"
    if not path.is_file():
        raise PresentationError(f"missing presentation rules: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PresentationError(f"invalid presentation rules {path}: {exc}") from exc
    return PresentationStore.from_payload(payload, facts, origin=str(path))


def load_candidate_context(knowledge_root: Path, facts: FactStore) -> CandidateContext:
    path = knowledge_root / "base" / CANDIDATE_FILE
    if not path.is_file():
        raise CandidateContextError(f"no candidate context in this Workspace: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CandidateContextError(f"invalid candidate context {path}: {exc}") from exc
    return build_candidate_context(payload, facts, origin=str(path))


def create_fact(
    base_dir: Path, source_name: str, payload: dict, *, canonical: bool = False
) -> Fact:
    """Persist a new fact into the canonical source file that will own it.

    The record is written to its final location immediately, so its identity
    and canonical location never move as it is confirmed.
    """
    store = load_fact_store(base_dir)
    record = build_new_fact(store, source_name, payload, canonical=canonical)
    path = base_dir / source_name
    title, source = parse_fact_source_document(path.read_text(encoding="utf-8"), origin=str(path))
    write_fact_source(path, title, with_new_fact(source, record, canonical=canonical))
    return record.model_copy(update={"source_file": f"base/{source_name}"})


def promote_fact(
    base_dir: Path,
    fact_id: str,
    target: FactStatus | str,
    *,
    explicitly_confirmed: bool,
) -> tuple[Fact, Fact]:
    """Advance one fact's lifecycle status and make it survive the process.

    Returns the fact before and after the transition. Transition legality and
    the explicit-confirmation requirement are enforced by `FactStore.promote`.
    """
    status = FactStatus(target)
    store = load_fact_store(base_dir)
    before = store.get(fact_id)
    promoted = store.promote(fact_id, status, explicitly_confirmed=explicitly_confirmed)
    path = base_dir / source_name_of(before)
    title, source = parse_fact_source_document(path.read_text(encoding="utf-8"), origin=str(path))
    confirmed_at = before.confirmed_at or utc_now()[:10]
    write_fact_source(path, title, with_promoted_fact(source, fact_id, status, confirmed_at))
    return before, promoted.model_copy(update={"confirmed_at": confirmed_at})


class FileKnowledge:
    """Knowledge as it is actually stored: version-controlled files.

    This is the only place that knows the knowledge layout inside a Workspace.
    Every command re-reads through it rather than holding a long-lived cache,
    so a manual or CLI edit between commands is seen rather than assumed away.
    """

    def __init__(self, knowledge_root: Path):
        self.knowledge_root = Path(knowledge_root)

    @property
    def base_dir(self) -> Path:
        return self.knowledge_root / "base"

    def facts(self) -> FactStore:
        return load_fact_store(self.base_dir)

    def load(self) -> Knowledge:
        facts = self.facts()
        return Knowledge(
            facts=facts,
            profiles=load_profile_store(self.knowledge_root, facts),
            policies=load_emphasis_policies(self.knowledge_root),
            candidate=load_candidate_context(self.knowledge_root, facts),
            presentations=load_presentations(self.knowledge_root, facts),
        )

    def create_fact(self, source_name: str, payload: dict, *, canonical: bool = False) -> Fact:
        return create_fact(self.base_dir, source_name, payload, canonical=canonical)

    def promote_fact(
        self, fact_id: str, target: FactStatus | str, *, explicitly_confirmed: bool
    ) -> tuple[Fact, Fact]:
        return promote_fact(
            self.base_dir, fact_id, target, explicitly_confirmed=explicitly_confirmed
        )

    def attach_fact(
        self, profile: str, fact_id: str, section: str, *, pin: bool = False
    ) -> tuple[Profile, str]:
        """Offer a canonical fact to one Profile section, and store the result.

        Returns the updated Profile and the source it was written back to, so
        the caller can report where the change landed without resolving paths.
        """
        facts = self.facts()
        source = load_profile_store(self.knowledge_root, facts).source(profile)
        path = Path(source)
        payload = json.loads(path.read_text(encoding="utf-8"))
        updated, document = attach_fact_to_section(
            payload, fact_id, section, origin=path.name, pin=pin
        )
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return updated, source
