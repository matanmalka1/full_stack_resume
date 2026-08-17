from __future__ import annotations

import json
import re
from pathlib import Path

from .models import Fact, FactSource, FactStatus
from .util import canonical_json, sha256_text, utc_now


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

    def __init__(
        self,
        facts: dict[str, Fact],
        source_versions: dict[str, str],
        base_dir: Path | None = None,
    ):
        self.facts = facts
        self.source_versions = source_versions
        self.base_dir = base_dir
        canonical = [
            facts[key] for key in sorted(facts)
            if facts[key].status is FactStatus.CANONICAL
        ]
        self.version = sha256_text(canonical_json({
            "sources": source_versions,
            "facts": [fact.model_dump(mode="json") for fact in canonical],
        }))
        self.lifecycle_version = sha256_text(canonical_json({
            "sources": source_versions,
            "facts": [facts[key].model_dump(mode="json") for key in sorted(facts)],
        }))

    @classmethod
    def load(cls, base_dir: Path) -> "FactStore":
        names = list(FACT_SOURCE_NAMES)
        facts: dict[str, Fact] = {}
        versions: dict[str, str] = {}
        missing = [name for name in names if not (base_dir / name).is_file()]
        if missing:
            raise FactStoreError(f"missing canonical fact sources: {', '.join(missing)}")
        for name in names:
            source = load_fact_source(base_dir / name)
            versions[name] = source.source_version
            for fact in source.facts:
                if fact.fact_id in facts:
                    prior = facts[fact.fact_id].source_file
                    raise FactStoreError(
                        f"duplicate fact_id {fact.fact_id!r} in {prior} and {name}"
                    )
                facts[fact.fact_id] = fact.model_copy(update={"source_file": f"base/{name}"})
        return cls(facts, versions, base_dir)

    def by_status(self, status: FactStatus | str | None = None) -> list[Fact]:
        target = FactStatus(status) if status is not None else None
        return [
            self.facts[key] for key in sorted(self.facts)
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


def load_fact_source(path: Path) -> FactSource:
    text = path.read_text(encoding="utf-8")
    match = FACT_BLOCK.search(text)
    if not match:
        raise FactStoreError(f"no JSON fact block in {path}")
    try:
        payload = json.loads(match.group(1))
        return FactSource.model_validate(payload)
    except (json.JSONDecodeError, ValueError) as exc:
        raise FactStoreError(f"invalid fact source {path}: {exc}") from exc


def render_fact_source(title: str, source: FactSource) -> str:
    payload = json.dumps(source.model_dump(mode="json"), ensure_ascii=False, indent=2)
    return (
        f"# {title}\n\n"
        "This file is an authoritative v1 fact source. Edit facts through the fact "
        "lifecycle; profiles may reference IDs but must not copy content.\n\n"
        f"```json\n{payload}\n```\n"
    )


def load_fact_source_document(path: Path) -> tuple[str, FactSource]:
    """The source file's title and parsed facts, for read-modify-write."""
    text = path.read_text(encoding="utf-8")
    title = SOURCE_TITLE.search(text)
    if not title:
        raise FactStoreError(f"fact source has no title heading: {path}")
    return title.group(1), load_fact_source(path)


def write_fact_source(path: Path, title: str, source: FactSource) -> None:
    path.write_text(render_fact_source(title, source), encoding="utf-8")


def _next_source_version(version: str) -> str:
    match = SEMVER.match(version)
    if not match:
        raise FactStoreError(f"fact source version is not semantic: {version!r}")
    major, minor, patch = (int(part) for part in match.groups())
    return f"{major}.{minor}.{patch + 1}"


def _source_name(fact: Fact) -> str:
    name = fact.source_file.rsplit("/", 1)[-1]
    if name not in FACT_SOURCE_NAMES:
        raise FactStoreError(f"fact {fact.fact_id} has no canonical source file")
    return name


def create_fact(
    base_dir: Path,
    source_name: str,
    payload: dict,
    *,
    canonical: bool = False,
) -> Fact:
    """Persist a new fact into the canonical source file that will own it.

    The fact is written to its final location immediately and starts `pending`,
    so its identity and canonical location never move as it is confirmed. Only
    an explicit confirmation in the same request (`canonical=True`, the spec's
    "add this to the source of truth") may write it as canonical directly.
    """
    if source_name not in FACT_SOURCE_NAMES:
        raise FactStoreError(
            f"unknown canonical fact source: {source_name} "
            f"(expected one of {', '.join(FACT_SOURCE_NAMES)})"
        )
    store = FactStore.load(base_dir)
    fact_id = payload.get("fact_id")
    if fact_id in store.facts:
        existing = store.facts[fact_id]
        raise FactStoreError(
            f"fact already exists: {fact_id} in {existing.source_file} ({existing.status})"
        )
    status = FactStatus.CANONICAL if canonical else FactStatus.PENDING
    record = Fact.model_validate({
        **{key: value for key, value in payload.items() if key not in {"status", "source_file"}},
        "status": status.value,
        "confirmed_at": payload.get("confirmed_at") or (utc_now()[:10] if canonical else None),
        "source_file": "",
    })
    path = base_dir / source_name
    title, source = load_fact_source_document(path)
    # The declared source version tracks canonical content only; a pending fact
    # is staging and must not invalidate drafts built from this file.
    version = _next_source_version(source.source_version) if canonical else source.source_version
    write_fact_source(path, title, FactSource(
        source_version=version,
        facts=[*source.facts, record],
    ))
    return record.model_copy(update={"source_file": f"base/{source_name}"})


def promote_fact(
    base_dir: Path,
    fact_id: str,
    target: FactStatus | str,
    *,
    explicitly_confirmed: bool,
) -> tuple[Fact, Fact]:
    """Advance one fact's lifecycle status and persist it to its source file.

    Returns the fact before and after the transition. Transition legality and
    the explicit-confirmation requirement are enforced by `FactStore.promote`;
    this function is what makes the result survive the process.
    """
    status = FactStatus(target)
    store = FactStore.load(base_dir)
    before = store.get(fact_id)
    promoted = store.promote(fact_id, status, explicitly_confirmed=explicitly_confirmed)
    name = _source_name(before)
    path = base_dir / name
    title, source = load_fact_source_document(path)
    confirmed_at = before.confirmed_at or utc_now()[:10]
    facts = [
        fact.model_copy(update={"status": status, "confirmed_at": confirmed_at})
        if fact.fact_id == fact_id else fact
        for fact in source.facts
    ]
    if all(fact.status is not status or fact.fact_id != fact_id for fact in facts):
        raise FactStoreError(f"fact {fact_id} is not present in {name}")
    version = (
        _next_source_version(source.source_version)
        if status is FactStatus.CANONICAL else source.source_version
    )
    write_fact_source(path, title, FactSource(source_version=version, facts=facts))
    return before, promoted.model_copy(update={"confirmed_at": confirmed_at})
