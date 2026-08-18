from __future__ import annotations

import json
import re

from .models import Fact, FactSource, FactStatus
from ..util import canonical_json, sha256_text, utc_now


FACT_BLOCK = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
FACT_SOURCE_NAMES = ("common.md", "sales.md", "development.md", "situational_skills.md")
SOURCE_TITLE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


class FactStoreError(ValueError):
    pass


class FactStore:
    """Every fact the repository knows, at every lifecycle status.

    `version` covers only the canonical facts and the source versions that
    declare them: it identifies the surface a CV may actually be built from, so
    creating or confirming a `pending` fact for one application does not
    invalidate another application's approved draft. `lifecycle_version` covers
    every fact at every status and is what the lifecycle audit trail records.
    """

    def __init__(self, facts: dict[str, Fact], source_versions: dict[str, str]):
        self.facts = facts
        self.source_versions = source_versions
        canonical = [
            facts[key] for key in sorted(facts) if facts[key].status is FactStatus.CANONICAL
        ]
        self.version = sha256_text(
            canonical_json(
                {
                    "sources": source_versions,
                    "facts": [fact.model_dump(mode="json") for fact in canonical],
                }
            )
        )
        self.lifecycle_version = sha256_text(
            canonical_json(
                {
                    "sources": source_versions,
                    "facts": [facts[key].model_dump(mode="json") for key in sorted(facts)],
                }
            )
        )

    @classmethod
    def from_sources(cls, sources: dict[str, FactSource]) -> "FactStore":
        """Build the store from already-parsed sources, keyed by file name.

        Reading those files is the storage adapter's job. This stays a pure
        assembly of what a fact source means: one canonical location per fact,
        and every declared source present.
        """
        missing = [name for name in FACT_SOURCE_NAMES if name not in sources]
        if missing:
            raise FactStoreError(f"missing canonical fact sources: {', '.join(missing)}")
        facts: dict[str, Fact] = {}
        versions: dict[str, str] = {}
        for name in FACT_SOURCE_NAMES:
            source = sources[name]
            versions[name] = source.source_version
            for fact in source.facts:
                if fact.fact_id in facts:
                    prior = facts[fact.fact_id].source_file
                    raise FactStoreError(
                        f"duplicate fact_id {fact.fact_id!r} in {prior} and {name}"
                    )
                facts[fact.fact_id] = fact.model_copy(update={"source_file": f"base/{name}"})
        return cls(facts, versions)

    def by_status(self, status: FactStatus | str | None = None) -> list[Fact]:
        target = FactStatus(status) if status is not None else None
        return [
            self.facts[key]
            for key in sorted(self.facts)
            if target is None or self.facts[key].status is target
        ]

    def get(self, fact_id: str, *, canonical_only: bool = False) -> Fact:
        try:
            fact = self.facts[fact_id]
        except KeyError as exc:
            raise FactStoreError(f"unknown fact_id: {fact_id}") from exc
        if canonical_only and fact.status is not FactStatus.CANONICAL:
            raise FactStoreError(f"fact is not canonical: {fact_id} ({fact.status})")
        return fact

    def rendering(self, fact_id: str, language: str) -> str:
        fact = self.get(fact_id, canonical_only=True)
        value = fact.renderings.get(language)
        if not value:
            raise FactStoreError(f"fact {fact_id} has no {language!r} rendering")
        return value

    def promote(self, fact_id: str, target: FactStatus, *, explicitly_confirmed: bool) -> Fact:
        fact = self.get(fact_id)
        allowed = {
            FactStatus.PENDING: FactStatus.CONFIRMED,
            FactStatus.CONFIRMED: FactStatus.CANONICAL,
        }
        if allowed.get(fact.status) is not target:
            raise FactStoreError(f"invalid fact transition: {fact.status} -> {target}")
        if not explicitly_confirmed:
            raise FactStoreError("fact promotion requires explicit confirmation")
        promoted = fact.model_copy(update={"status": target})
        self.facts[fact_id] = promoted
        return promoted


def parse_fact_source(text: str, *, origin: str) -> FactSource:
    """Parse one fact source document. `origin` only names it in errors."""
    match = FACT_BLOCK.search(text)
    if not match:
        raise FactStoreError(f"no JSON fact block in {origin}")
    try:
        payload = json.loads(match.group(1))
        return FactSource.model_validate(payload)
    except (json.JSONDecodeError, ValueError) as exc:
        raise FactStoreError(f"invalid fact source {origin}: {exc}") from exc


def render_fact_source(title: str, source: FactSource) -> str:
    payload = json.dumps(source.model_dump(mode="json"), ensure_ascii=False, indent=2)
    return (
        f"# {title}\n\n"
        "This file is an authoritative v1 fact source. Edit facts through the fact "
        "lifecycle; profiles may reference IDs but must not copy content.\n\n"
        f"```json\n{payload}\n```\n"
    )


def parse_fact_source_document(text: str, *, origin: str) -> tuple[str, FactSource]:
    """The document's title and parsed facts, for read-modify-write."""
    title = SOURCE_TITLE.search(text)
    if not title:
        raise FactStoreError(f"fact source has no title heading: {origin}")
    return title.group(1), parse_fact_source(text, origin=origin)


def _next_source_version(version: str) -> str:
    match = SEMVER.match(version)
    if not match:
        raise FactStoreError(f"fact source version is not semantic: {version!r}")
    major, minor, patch = (int(part) for part in match.groups())
    return f"{major}.{minor}.{patch + 1}"


def source_name_of(fact: Fact) -> str:
    """The canonical source file a fact belongs to, by name only."""
    name = fact.source_file.rsplit("/", 1)[-1]
    if name not in FACT_SOURCE_NAMES:
        raise FactStoreError(f"fact {fact.fact_id} has no canonical source file")
    return name


def build_new_fact(store: FactStore, source_name: str, payload: dict, *, canonical: bool) -> Fact:
    """The record a new fact would become, before anything is stored.

    A new fact starts `pending` so its identity and canonical location never
    move as it is confirmed. Only an explicit confirmation in the same request
    (`canonical=True`, the spec's "add this to the source of truth") may make
    it canonical directly.
    """
    if source_name not in FACT_SOURCE_NAMES:
        raise FactStoreError(
            f"unknown canonical fact source: {source_name} "
            f"(expected one of {', '.join(FACT_SOURCE_NAMES)})"
        )
    fact_id = payload.get("fact_id")
    if fact_id in store.facts:
        existing = store.facts[fact_id]
        raise FactStoreError(
            f"fact already exists: {fact_id} in {existing.source_file} ({existing.status})"
        )
    status = FactStatus.CANONICAL if canonical else FactStatus.PENDING
    return Fact.model_validate(
        {
            **{
                key: value for key, value in payload.items() if key not in {"status", "source_file"}
            },
            "status": status.value,
            "confirmed_at": payload.get("confirmed_at") or (utc_now()[:10] if canonical else None),
            "source_file": "",
        }
    )


def with_new_fact(source: FactSource, record: Fact, *, canonical: bool) -> FactSource:
    """The source file's next content with one fact appended.

    The declared source version tracks canonical content only; a pending fact
    is staging and must not invalidate drafts built from this file.
    """
    version = _next_source_version(source.source_version) if canonical else source.source_version
    return FactSource(source_version=version, facts=[*source.facts, record])


def with_promoted_fact(
    source: FactSource, fact_id: str, status: FactStatus, confirmed_at: str
) -> FactSource:
    """The source file's next content with one fact's status advanced."""
    facts = [
        fact.model_copy(update={"status": status, "confirmed_at": confirmed_at})
        if fact.fact_id == fact_id
        else fact
        for fact in source.facts
    ]
    if all(fact.status is not status or fact.fact_id != fact_id for fact in facts):
        raise FactStoreError(f"fact {fact_id} is not present in this source")
    version = (
        _next_source_version(source.source_version)
        if status is FactStatus.CANONICAL
        else source.source_version
    )
    return FactSource(source_version=version, facts=facts)
