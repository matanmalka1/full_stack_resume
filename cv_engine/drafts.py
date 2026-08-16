from __future__ import annotations

import json
import uuid
from pathlib import Path

from .facts import FactStore
from .models import ClaimLine, DraftDocument, JobAnalysis, Profile, ResumeSection
from .util import canonical_json, sha256_text


CONTACT_FACTS = [
    "common.contact.location",
    "common.contact.phone",
    "common.contact.email",
    "common.contact.linkedin",
]
CLAIM_NAMESPACE = uuid.UUID("e47cfc95-7f5c-4dd2-acd4-19be02c8f988")


def _claim(style: str, text: str, fact_ids: list[str], claim_type: str = "canonical") -> ClaimLine:
    return ClaimLine(
        claim_id=str(uuid.uuid5(CLAIM_NAMESPACE, canonical_json({
            "style": style, "text": text, "fact_ids": fact_ids, "claim_type": claim_type,
        }))),
        style=style,
        text=text,
        fact_ids=fact_ids,
        claim_type=claim_type,
        text_hash=sha256_text(text),
    )


def build_draft(
    *,
    application_id: str,
    job_snapshot_id: str,
    analysis: JobAnalysis,
    profile: Profile,
    facts: FactStore,
) -> DraftDocument:
    if analysis.profile is not profile.profile or analysis.track is not profile.track:
        raise ValueError("analysis and profile do not match")
    if analysis.emphasis not in profile.allowed_emphases:
        raise ValueError(f"emphasis {analysis.emphasis} is not allowed for {profile.profile}")

    language = analysis.language
    contact_ids = list(CONTACT_FACTS)
    if analysis.track.value == "development":
        contact_ids.append("common.contact.github")
    contacts = [
        _claim("contact", facts.rendering(fact_id, language), [fact_id])
        for fact_id in contact_ids
    ]

    support_ids = [
        fact_id
        for section in profile.sections
        for fact_id in section.fact_ids
        if "historical-title" in facts.get(fact_id).tags
    ]
    headline = _claim(
        "headline",
        profile.normalized_role,
        support_ids,
        "headline",
    )

    selected = set(contact_ids + support_ids)
    sections: list[ResumeSection] = []
    for spec in profile.sections:
        claims = []
        for fact_id in spec.fact_ids:
            fact = facts.get(fact_id, canonical_only=True)
            text = facts.rendering(fact_id, language)
            claims.append(_claim(fact.resume_style, text, [fact_id]))
            selected.add(fact_id)
        if claims or not spec.optional:
            sections.append(ResumeSection(
                name=spec.name_he if language == "he" else spec.name_en,
                claims=claims,
            ))

    draft = DraftDocument(
        application_id=application_id,
        job_snapshot_id=job_snapshot_id,
        language=language,
        track=analysis.track,
        profile=analysis.profile,
        emphasis=analysis.emphasis,
        name="Matan Malka" if language == "en" else "מתן מלכה",
        headline=headline,
        contacts=contacts,
        sections=sections,
        selected_fact_ids=sorted(selected),
        omitted_facts={
            fact_id: "not selected by the active Profile and rendering budget"
            for fact_id in sorted(set(facts.facts) - selected)
        },
        fact_store_version=facts.version,
    )
    markdown = serialize_markdown(draft)
    return draft.model_copy(update={"content_hash": sha256_text(markdown)})


def _marker(claim: ClaimLine) -> str:
    return f"<!-- claim:{claim.claim_id}:{claim.text_hash} -->"


def _render_claim(claim: ClaimLine) -> list[str]:
    if claim.style == "heading":
        line = f"### {claim.text}"
    elif claim.style == "date":
        line = f"**{claim.text}**"
    elif claim.style in {"bullet", "item"}:
        line = f"- {claim.text}"
    else:
        line = claim.text
    return [_marker(claim), line]


def serialize_markdown(draft: DraftDocument) -> str:
    front = {
        "schema_version": draft.schema_version,
        "application_id": draft.application_id,
        "job_snapshot_id": draft.job_snapshot_id,
        "language": draft.language,
        "track": draft.track.value,
        "profile": draft.profile.value,
        "emphasis": draft.emphasis.value,
        "fact_store_version": draft.fact_store_version,
    }
    lines = ["---"]
    lines.extend(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in front.items())
    lines.extend(["---", "", f"# {draft.name}", ""])
    lines.extend(_render_claim(draft.headline))
    lines.append("")
    for contact in draft.contacts:
        lines.extend(_render_claim(contact))
    for section in draft.sections:
        lines.extend(["", "---", "", f"## {section.name}", ""])
        for claim in section.claims:
            lines.extend(_render_claim(claim))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_working_draft(root: Path, draft: DraftDocument) -> tuple[Path, Path]:
    target = root / "artifacts" / "working" / draft.application_id
    target.mkdir(parents=True, exist_ok=True)
    markdown_path = target / "resume.md"
    manifest_path = target / "resume.claims.json"
    markdown = serialize_markdown(draft)
    draft = draft.model_copy(update={"content_hash": sha256_text(markdown)})
    markdown_path.write_text(markdown, encoding="utf-8")
    manifest_path.write_text(
        json.dumps(draft.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return markdown_path, manifest_path


def load_draft(manifest_path: Path) -> DraftDocument:
    return DraftDocument.model_validate_json(manifest_path.read_text(encoding="utf-8"))


def register_linked_claim(
    draft: DraftDocument,
    claim_id: str,
    new_text: str,
    fact_ids: list[str],
    facts: FactStore,
) -> DraftDocument:
    if not new_text.strip() or len(fact_ids) != 1:
        raise ValueError(
            "free-form derived statements are disabled; link exactly one canonical fact "
            "or confirm a new fact before using it"
        )
    fact = facts.get(fact_ids[0], canonical_only=True)
    canonical_text = facts.rendering(fact.fact_id, draft.language)
    if new_text.strip() != canonical_text:
        raise ValueError(
            "free-form derived statements are disabled; claim text must exactly match "
            f"the {draft.language} rendering of canonical fact {fact.fact_id}"
        )
    replacement = None
    for section in draft.sections:
        for index, claim in enumerate(section.claims):
            if claim.claim_id == claim_id:
                if claim.style in {"heading", "date"}:
                    raise ValueError("historical titles and dates cannot be relinked")
                if fact.resume_style != claim.style:
                    raise ValueError(
                        f"canonical fact {fact.fact_id} uses {fact.resume_style!r}, "
                        f"not the target claim style {claim.style!r}"
                    )
                replacement = _claim(claim.style, canonical_text, fact_ids, "canonical")
                replacement = replacement.model_copy(update={"claim_id": claim_id})
                section.claims[index] = replacement
    if replacement is None:
        raise KeyError(claim_id)
    selected = {
        fact_id
        for claim in [draft.headline, *draft.contacts, *(claim for section in draft.sections for claim in section.claims)]
        for fact_id in claim.fact_ids
    }
    draft.selected_fact_ids = sorted(selected)
    draft.omitted_facts = {
        fact_id: "not selected by the active Profile and rendering budget"
        for fact_id in sorted(set(facts.facts) - selected)
    }
    markdown = serialize_markdown(draft)
    return draft.model_copy(update={"content_hash": sha256_text(markdown)})
