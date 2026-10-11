"""How file Knowledge maps onto per-user rows, and back (architecture §18.2).

Pure: no files, no database. The import reads Knowledge through the same validated
loader the application uses, splits it here, and the round trip back through
`join_profile` / `fact_from_row` must reproduce what was read.

A Profile splits in two. Its template - track, sections and their guidance, emphases,
tag weights - is product policy and stays a version-controlled file. Its binding - which
of this candidate's facts each section offers, which are pinned, the safe headlines and
the omitted roles - names one candidate's facts, so it belongs to that user.
"""

from __future__ import annotations

from typing import Any

from .contracts.knowledge import CandidateContext, Fact, Profile
from .facts import FACT_SOURCE_NAMES, FactStore, source_id_of_name, source_name_of

#: The `source` column: the grouping each fact's file was. `user` is for facts created
#: in the Web once Knowledge lives in the database.
FACT_SOURCES = (*(source_id_of_name(name) for name in FACT_SOURCE_NAMES), "user")

#: Profile fields that name one candidate's facts or wording, beside the per-section pools.
BINDING_FIELDS = ("safe_headlines", "omitted_roles")
SECTION_BINDING_FIELDS = ("fact_ids", "pinned_fact_ids")

#: `CandidateContext` fields resolved from facts at load time; never stored.
RESOLVED_CANDIDATE_FIELDS = ("names", "link_targets", "resolved_filename_name", "version_hash")


class KnowledgeSplitError(ValueError):
    pass


def fact_rows(facts: FactStore) -> list[dict[str, Any]]:
    """One row per fact, with its source and its position within that source.

    The store keeps each source's facts in file order, so `ordinal` is that order and
    a later read can lay the facts out exactly as the file did.
    """
    ordinals: dict[str, int] = {}
    rows = []
    for fact in facts.facts.values():
        source = source_id_of_name(source_name_of(fact))
        ordinals[source] = ordinals.get(source, 0) + 1
        payload = fact.model_dump(mode="json", exclude={"source_file"})
        rows.append({**payload, "source": source, "ordinal": ordinals[source]})
    return rows


def fact_from_row(row: dict[str, Any]) -> Fact:
    """The Fact a stored row describes, `source_file` named as the file it came from."""
    content = {key: value for key, value in row.items() if key in Fact.model_fields}
    return Fact.model_validate({**content, "source_file": f"base/{row['source']}.json"})


def candidate_payload(candidate: CandidateContext) -> dict[str, Any]:
    """The declared candidate context, without what is resolved from facts."""
    return candidate.model_dump(mode="json", exclude=set(RESOLVED_CANDIDATE_FIELDS))


def split_profile(profile: Profile) -> tuple[dict[str, Any], dict[str, Any]]:
    """The Profile's template and this candidate's binding to it."""
    payload = profile.model_dump(mode="json")
    names = [section["name_en"] for section in payload["sections"]]
    if len(set(names)) != len(names):
        raise KnowledgeSplitError(f"profile {profile.profile_id} repeats a section name")
    binding: dict[str, Any] = {field: payload.pop(field) for field in BINDING_FIELDS}
    binding["sections"] = {}
    for section in payload["sections"]:
        pinned = set(section.pop("pinned_fact_ids"))
        binding["sections"][section["name_en"]] = [
            {"fact_id": fact_id, "pinned": fact_id in pinned} for fact_id in section.pop("fact_ids")
        ]
    return payload, binding


def join_profile(template: dict[str, Any], binding: dict[str, Any]) -> Profile:
    """The Profile a template and a binding make together; the inverse of `split_profile`."""
    sections = binding["sections"]
    unknown = sorted(set(sections) - {section["name_en"] for section in template["sections"]})
    if unknown:
        raise KnowledgeSplitError(
            f"binding for {template['profile_id']} names sections its template lacks: "
            f"{', '.join(unknown)}"
        )
    joined = {**template, **{field: binding[field] for field in BINDING_FIELDS}}
    joined["sections"] = [
        {
            **section,
            "fact_ids": [entry["fact_id"] for entry in sections.get(section["name_en"], [])],
            "pinned_fact_ids": [
                entry["fact_id"]
                for entry in sections.get(section["name_en"], [])
                if entry["pinned"]
            ],
        }
        for section in template["sections"]
    ]
    return Profile.model_validate(joined)
