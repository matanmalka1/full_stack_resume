from __future__ import annotations

import json
import re
from pathlib import Path

from .models import Fact, FactSource, FactStatus
from .util import canonical_json, sha256_text


FACT_BLOCK = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


class FactStoreError(ValueError):
    pass


class FactStore:
    def __init__(self, facts: dict[str, Fact], source_versions: dict[str, str]):
        self.facts = facts
        self.source_versions = source_versions
        version_payload = {
            "sources": source_versions,
            "facts": [facts[key].model_dump(mode="json") for key in sorted(facts)],
        }
        self.version = sha256_text(canonical_json(version_payload))

    @classmethod
    def load(cls, base_dir: Path) -> "FactStore":
        names = ["common.md", "sales.md", "development.md", "situational_skills.md"]
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
        return cls(facts, versions)

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
