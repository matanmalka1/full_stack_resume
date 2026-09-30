from __future__ import annotations

import json
import re
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from ..util import canonical_json, sha256_text
from .contracts.analysis import JobAnalysis
from .contracts.drafts import (
    ClaimLine,
    ClaimReviewEvidence,
    ClaimStyle,
    ClaimType,
    DraftDocument,
    ResumeSection,
)
from .contracts.knowledge import CandidateContext, Profile
from .draft_markdown import serialize_markdown as _serialize_markdown
from .facts import FactStore
from .frame import STRUCTURAL_STYLES, lay_out_choice, require_fact_renderings
from .presentations import PresentationStore, PresentedClaim


def draft_content_hash(draft: DraftDocument) -> str:
    """The fingerprint of one draft's own data, independent of any rendering.

    Excludes `content_hash` itself so the value is stable whether the draft
    already carries one or not, and independent of Markdown so a change to how
    the document is rendered can never move it.
    """
    return sha256_text(canonical_json(draft.model_dump(mode="json", exclude={"content_hash"})))


CLAIM_NAMESPACE = uuid.UUID("e47cfc95-7f5c-4dd2-acd4-19be02c8f988")
CANONICAL_JOIN_TEMPLATE = ("canonical-renderings", "1.0.0")
EXTRACTIVE_DERIVATION = ("extractive-clauses", "1.0.0")
EDITABLE_STYLES = frozenset({"paragraph", "bullet", "item"})
MANUAL_CLAIM_PENDING_REASON = "שורה שנוספה ידנית וטרם קושרה לעובדה מאומתת."


@dataclass(frozen=True)
class CompositeTemplate:
    template_id: str
    version: str
    input_styles: frozenset[str]
    output_styles: frozenset[str]


COMPOSITE_TEMPLATES: dict[tuple[str, str], CompositeTemplate] = {
    CANONICAL_JOIN_TEMPLATE: CompositeTemplate(
        template_id=CANONICAL_JOIN_TEMPLATE[0],
        version=CANONICAL_JOIN_TEMPLATE[1],
        input_styles=EDITABLE_STYLES,
        output_styles=EDITABLE_STYLES,
    ),
}


def _claim(
    style: ClaimStyle,
    text: str,
    fact_ids: list[str],
    claim_type: ClaimType = "canonical",
    *,
    template_id: str | None = None,
    template_version: str | None = None,
    derivation_id: str | None = None,
    derivation_version: str | None = None,
    pending_reason: str | None = None,
    review_evidence: ClaimReviewEvidence | None = None,
) -> ClaimLine:
    identity = {
        "style": style,
        "text": text,
        "fact_ids": fact_ids,
        "claim_type": claim_type,
    }
    if template_id is not None or template_version is not None:
        identity.update({"template_id": template_id, "template_version": template_version})
    if derivation_id is not None or derivation_version is not None:
        identity.update({"derivation_id": derivation_id, "derivation_version": derivation_version})
    if pending_reason is not None:
        identity["pending_reason"] = pending_reason
    if review_evidence is not None:
        identity["review_evidence"] = review_evidence.model_dump(mode="json")
    return ClaimLine(
        claim_id=str(uuid.uuid5(CLAIM_NAMESPACE, canonical_json(identity))),
        style=style,
        text=text,
        fact_ids=fact_ids,
        claim_type=claim_type,
        text_hash=sha256_text(text),
        template_id=template_id,
        template_version=template_version,
        derivation_id=derivation_id,
        derivation_version=derivation_version,
        pending_reason=pending_reason,
        review_evidence=review_evidence,
    )


def authorize_reviewed_claim(
    draft: DraftDocument,
    claim_id: str,
    facts: FactStore,
    evidence: ClaimReviewEvidence,
) -> DraftDocument:
    """Promote exact pending wording after separate semantic review."""
    try:
        current = next(claim for claim in draft_claims(draft) if claim.claim_id == claim_id)
    except StopIteration as exc:
        raise KeyError(claim_id) from exc
    if current.claim_type != "pending" or not current.fact_ids:
        raise ValueError("semantic review may authorize only linked pending wording")
    if current.style not in EDITABLE_STYLES:
        raise ValueError("semantic review cannot authorize structural wording")
    for fact_id in current.fact_ids:
        facts.get(fact_id, canonical_only=True)
    replacement = _claim(
        current.style,
        current.text,
        list(current.fact_ids),
        "reviewed",
        review_evidence=evidence,
    ).model_copy(update={"claim_id": current.claim_id})
    _replace_claim(draft, claim_id, replacement)
    return _reseal(draft)


def build_draft(
    *,
    application_id: str,
    job_snapshot_id: str,
    job_analysis_id: str,
    analysis: JobAnalysis,
    profile: Profile,
    facts: FactStore,
    candidate: CandidateContext,
    presentations: PresentationStore | None = None,
    chosen: Mapping[str, Iterable[str]] | None = None,
) -> DraftDocument:
    """Lay out a document in canonical wording.

    `chosen` maps each section's English name to the facts picked for it; the section's
    structure is added and everything is laid out in pool order (`lay_out_choice`).
    `None` lays out every pool in full: the frame `draft_resume` chooses from.
    """
    if analysis.profile is not profile.profile or analysis.track is not profile.track:
        raise ValueError("analysis and profile do not match")

    effective_emphasis = analysis.emphasis
    if effective_emphasis not in profile.allowed_emphases:
        raise ValueError(f"emphasis {effective_emphasis} is not allowed for {profile.profile}")

    language = analysis.language
    contact_ids = candidate.contacts_for_track(analysis.track.value)
    selected_by_section = lay_out_choice(profile, facts, language, chosen)

    # Contacts are eligible through CandidateContext rather than a Profile
    # section, so they need the same language invariant before the first claim
    # is composed.
    require_fact_renderings(facts, set(contact_ids), language)
    contacts = [
        _claim("contact", facts.rendering(fact_id, language), [fact_id]) for fact_id in contact_ids
    ]

    # The headline is supported by the historical titles that actually reached
    # the document, not by every title the Profile could have shown.
    support_ids = [
        fact_id
        for section in profile.sections
        for fact_id in selected_by_section[section.name_en]
        if "historical-title" in facts.get(fact_id).tags
    ]
    headline = _claim(
        "headline",
        profile.headline or profile.normalized_role,
        support_ids,
        "headline",
    )

    selected = set(contact_ids)
    sections: list[ResumeSection] = []
    for spec in profile.sections:
        claims = []
        selected_ids = selected_by_section[spec.name_en]
        presented = (
            presentations.render_section(
                profile=profile,
                section=spec.name_en,
                emphasis=effective_emphasis,
                selected_fact_ids=selected_ids,
                language=language,
                facts=facts,
            )
            if presentations is not None
            else []
        )
        if presentations is None:
            presented = [
                PresentedClaim(
                    style=facts.get(fact_id, canonical_only=True).resume_style,
                    text=facts.rendering(fact_id, language),
                    fact_ids=(fact_id,),
                )
                for fact_id in selected_ids
            ]
        for item in presented:
            fact_ids = list(item.fact_ids)
            if item.rule_id is None:
                claims.append(_claim(item.style, item.text, fact_ids))
            elif len(fact_ids) == 1:
                claims.append(
                    _claim(
                        item.style,
                        item.text,
                        fact_ids,
                        "derived",
                        derivation_id=item.rule_id,
                        derivation_version=item.rule_version,
                    )
                )
            else:
                claims.append(
                    _claim(
                        item.style,
                        item.text,
                        fact_ids,
                        "composite",
                        template_id=item.rule_id,
                        template_version=item.rule_version,
                    )
                )
            selected.update(fact_ids)
        if claims or not spec.optional:
            sections.append(
                ResumeSection(
                    name=spec.name_he if language == "he" else spec.name_en,
                    claims=claims,
                )
            )

    draft = DraftDocument(
        application_id=application_id,
        job_snapshot_id=job_snapshot_id,
        job_analysis_id=job_analysis_id,
        language=language,
        track=analysis.track,
        profile=analysis.profile,
        emphasis=effective_emphasis,
        name=candidate.display_name(language),
        headline=headline,
        contacts=contacts,
        sections=sections,
        selected_fact_ids=sorted(selected),
        fact_store_version=facts.version,
    )
    return draft.model_copy(update={"content_hash": draft_content_hash(draft)})


def seal_draft(draft: DraftDocument) -> tuple[DraftDocument, str, str]:
    """The two payloads a stored draft consists of, and the draft they describe.

    The content hash is derived from the draft's own data, independent of the
    Markdown rendered here, so re-sealing an unchanged draft can never move it
    even if how Markdown is rendered changes. Where the two payloads land is a
    storage decision made outside this layer.
    """
    sealed = draft.model_copy(update={"content_hash": draft_content_hash(draft)})
    markdown = _serialize_markdown(sealed)
    manifest = json.dumps(sealed.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
    return sealed, markdown, manifest


def draft_claims(draft: DraftDocument) -> list[ClaimLine]:
    """Every claim in one document, headline and contacts included.

    Public because the edit paths outside this module have to reason about the
    same set: a caller that walked `sections` alone would silently ignore the
    two claims that are not in one.
    """
    return [
        draft.headline,
        *draft.contacts,
        *(claim for section in draft.sections for claim in section.claims),
    ]


def reorder_draft(
    draft: DraftDocument,
    *,
    claim_orders: dict[str, list[str]] | None = None,
) -> DraftDocument:
    """Reorder claims within their sections without changing identity, ownership, or facts.

    Sections themselves never move: their order is Profile policy, and validation refuses
    any other order, so an edit that moved one could only produce a draft that cannot be
    approved.
    """
    reordered = draft.model_copy(deep=True)
    sections = {section.name: section for section in reordered.sections}
    if len(sections) != len(reordered.sections):
        raise ValueError("section names must be unique before they can be reordered")

    for section_name, requested in (claim_orders or {}).items():
        section = sections.get(section_name)
        if section is None:
            raise KeyError(section_name)
        claims = {claim.claim_id: claim for claim in section.claims}
        if len(claims) != len(section.claims):
            raise ValueError(f"claim IDs in section {section_name!r} must be unique")
        if len(requested) != len(set(requested)) or set(requested) != set(claims):
            raise ValueError(
                f"claim order for section {section_name!r} must contain every claim exactly once"
            )
        section.claims = [claims[claim_id] for claim_id in requested]

    return reordered.model_copy(update={"content_hash": draft_content_hash(reordered)})


def keep_frame_claims(
    frame: DraftDocument, profile: Profile, kept_claim_ids: set[str]
) -> DraftDocument:
    """The frame narrowed to the claims a writer kept, plus its structure.

    Claims are filtered, not rebuilt, so every kept claim keeps its identity and its
    place in pool order: a role's title, dates and bullets stay together. Headings,
    dates and contacts stay whether or not they were kept. An optional section left
    with no claims is dropped, as `build_draft` drops one.
    """
    optional = {
        (spec.name_he if frame.language == "he" else spec.name_en)
        for spec in profile.sections
        if spec.optional
    }
    narrowed = frame.model_copy(deep=True)
    sections = []
    for section in narrowed.sections:
        section.claims = [
            claim
            for claim in section.claims
            if claim.claim_id in kept_claim_ids or claim.style in STRUCTURAL_STYLES
        ]
        if section.claims or section.name not in optional:
            sections.append(section)
    narrowed.sections = sections
    return _reseal(narrowed)


def _replace_claim(draft: DraftDocument, claim_id: str, replacement: ClaimLine) -> None:
    if draft.headline.claim_id == claim_id:
        draft.headline = replacement
        return
    for index, claim in enumerate(draft.contacts):
        if claim.claim_id == claim_id:
            draft.contacts[index] = replacement
            return
    for section in draft.sections:
        for index, claim in enumerate(section.claims):
            if claim.claim_id == claim_id:
                section.claims[index] = replacement
                return
    raise KeyError(claim_id)


def _reseal(draft: DraftDocument) -> DraftDocument:
    """Restate the facts the claims link, and the content hash, after an edit."""
    draft.selected_fact_ids = sorted(
        {fact_id for claim in draft_claims(draft) for fact_id in claim.fact_ids}
    )
    return draft.model_copy(update={"content_hash": draft_content_hash(draft)})


def _normalized_clause(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().rstrip(".;!?")).casefold()


def _canonical_clauses(text: str) -> list[str]:
    return [part for part in re.split(r"(?<=[.;!?])\s+", text.strip()) if part.strip()]


def validate_derived_wording(
    text: str,
    fact_ids: list[str],
    facts: FactStore,
    language: str,
    style: str,
    derivation_id: str,
    derivation_version: str,
    presentations: PresentationStore | None = None,
) -> None:
    if (derivation_id, derivation_version) != EXTRACTIVE_DERIVATION:
        if presentations is None:
            raise ValueError(f"unknown derivation contract: {derivation_id}@{derivation_version}")
        expected = presentations.render_rule(
            derivation_id,
            derivation_version,
            fact_ids,
            language,
            style,
        )
        if text != expected:
            raise ValueError(
                f"derived wording does not match presentation {derivation_id}@{derivation_version}"
            )
        return
    if len(fact_ids) != 1:
        raise ValueError("extractive derived wording must link exactly one canonical fact")
    fact = facts.get(fact_ids[0], canonical_only=True)
    if style not in EDITABLE_STYLES or fact.resume_style != style:
        raise ValueError(
            f"extractive derived wording requires matching editable styles; "
            f"fact={fact.resume_style!r}, output={style!r}"
        )
    source_clauses = _canonical_clauses(facts.rendering(fact.fact_id, language))
    candidate = _normalized_clause(text)
    allowed = {
        _normalized_clause(" ".join(source_clauses[start:end]))
        for start in range(len(source_clauses))
        for end in range(start + 1, len(source_clauses) + 1)
    }
    if not candidate or candidate not in allowed:
        raise ValueError(
            "derived wording must preserve one or more complete canonical clauses in their original order"
        )


def render_composite_claim(
    fact_ids: list[str],
    facts: FactStore,
    language: str,
    output_style: str,
    template_id: str,
    template_version: str,
    presentations: PresentationStore | None = None,
) -> str:
    try:
        template = COMPOSITE_TEMPLATES[(template_id, template_version)]
    except KeyError as exc:
        if presentations is None:
            raise ValueError(
                f"unknown deterministic claim template: {template_id}@{template_version}"
            ) from exc
        return presentations.render_rule(
            template_id,
            template_version,
            fact_ids,
            language,
            output_style,
        )
    if len(fact_ids) < 2 or len(fact_ids) != len(set(fact_ids)):
        raise ValueError(
            "deterministic composite claims require at least two distinct canonical facts"
        )
    if output_style not in template.output_styles:
        raise ValueError(
            f"template {template_id}@{template_version} does not allow output style {output_style!r}"
        )
    support = [facts.get(fact_id, canonical_only=True) for fact_id in fact_ids]
    invalid_styles = sorted(
        {fact.resume_style for fact in support if fact.resume_style not in template.input_styles}
    )
    if invalid_styles or any(fact.resume_style != output_style for fact in support):
        raise ValueError(
            f"template {template_id}@{template_version} requires every input style to equal "
            f"output style {output_style!r}"
        )
    return " ".join(facts.rendering(fact.fact_id, language) for fact in support)


def apply_claim_edit(
    draft: DraftDocument,
    claim_id: str,
    fact_ids: list[str],
    facts: FactStore,
    *,
    text: str | None = None,
    template_id: str | None = None,
    template_version: str | None = None,
) -> DraftDocument:
    # Callers diff the draft they passed against the one returned to find what an
    # edit touched; editing the input in place made that diff always empty.
    draft = draft.model_copy(deep=True)
    try:
        current = next(claim for claim in draft_claims(draft) if claim.claim_id == claim_id)
    except StopIteration as exc:
        raise KeyError(claim_id) from exc
    if template_id is not None:
        if text is not None:
            raise ValueError(
                "a claim edit must use either text or a deterministic template, not both"
            )
        version = template_version or CANONICAL_JOIN_TEMPLATE[1]
        rendered = render_composite_claim(
            fact_ids,
            facts,
            draft.language,
            current.style,
            template_id,
            version,
        )
        replacement = _claim(
            current.style,
            rendered,
            fact_ids,
            "composite",
            template_id=template_id,
            template_version=version,
        )
    else:
        edited = (text or "").strip()
        if not edited:
            raise ValueError("manual claim text cannot be empty")
        replacement = None
        # The headline is not a factual claim: it names the role the document argues
        # for, and whether its wording is allowed is the Profile's safe-headline list,
        # which validation enforces (`unsafe-headline`). Treating an edit as a factual
        # derivation made every headline edit pending - even retyping the exact text -
        # because its support is several historical titles, not one fact.
        # Keyed on the slot rather than the claim type, so a headline an earlier edit
        # left pending is recovered by the next edit.
        if draft.headline.claim_id == claim_id:
            replacement = _claim("headline", edited, list(current.fact_ids), "headline")
        if replacement is None and len(fact_ids) == 1:
            try:
                fact = facts.get(fact_ids[0], canonical_only=True)
                canonical_text = facts.rendering(fact.fact_id, draft.language)
            except ValueError:
                fact = None
                canonical_text = None
            if fact is not None and edited == canonical_text and fact.resume_style == current.style:
                replacement = _claim(current.style, edited, fact_ids, "canonical")
        if replacement is None:
            try:
                validate_derived_wording(
                    edited,
                    fact_ids,
                    facts,
                    draft.language,
                    current.style,
                    EXTRACTIVE_DERIVATION[0],
                    EXTRACTIVE_DERIVATION[1],
                )
            except ValueError as exc:
                replacement = _claim(
                    current.style,
                    edited,
                    fact_ids,
                    "pending",
                    pending_reason=str(exc),
                )
            else:
                replacement = _claim(
                    current.style,
                    edited,
                    fact_ids,
                    "derived",
                    derivation_id=EXTRACTIVE_DERIVATION[0],
                    derivation_version=EXTRACTIVE_DERIVATION[1],
                )
    _replace_claim(draft, claim_id, replacement.model_copy(update={"claim_id": claim_id}))
    return _reseal(draft)


def remove_claim(draft: DraftDocument, claim_id: str) -> DraftDocument:
    """Remove one section claim, and reseal.

    The document holds no separate fact selection, so a fact-backed line may go like
    any other: the facts it linked simply stop being used. Structure may not. The
    headline and contacts are required by the model and the candidate context, and a
    heading or date is what keeps a role's bullets attributed to it.

    A section left with no claims keeps its heading. Removing a line is not
    permission to restructure the document.
    """
    draft = draft.model_copy(deep=True)
    if draft.headline.claim_id == claim_id:
        raise ValueError("the headline is structural and cannot be removed")
    if any(claim.claim_id == claim_id for claim in draft.contacts):
        raise ValueError("a contact line is structural and cannot be removed")
    for section in draft.sections:
        for index, claim in enumerate(section.claims):
            if claim.claim_id != claim_id:
                continue
            if claim.style in STRUCTURAL_STYLES:
                raise ValueError(
                    "headings and dates are structure; a role keeps its title and dates"
                )
            del section.claims[index]
            return _reseal(draft)
    raise KeyError(claim_id)


def add_claim(
    draft: DraftDocument,
    section: str,
    text: str,
    *,
    style: ClaimStyle = "bullet",
) -> tuple[DraftDocument, str]:
    """Append a free-text line a person wrote, with nothing yet authorizing it.

    It lands as `pending`, on the same footing as any other line nothing could
    authorize: product-spec §10 already defines how a pending claim is resolved
    (linked to a fact, edited into something a fact does authorize, or
    removed), and the fact-resolution flow built for that case is exactly what
    a manually added line needs.
    """
    draft = draft.model_copy(deep=True)
    stripped = text.strip()
    if not stripped:
        raise ValueError("manual claim text cannot be empty")
    target = next((candidate for candidate in draft.sections if candidate.name == section), None)
    if target is None:
        raise KeyError(section)
    claim = ClaimLine(
        claim_id=str(uuid.uuid4()),
        style=style,
        text=stripped,
        fact_ids=[],
        claim_type="pending",
        text_hash=sha256_text(stripped),
        pending_reason=MANUAL_CLAIM_PENDING_REASON,
    )
    target.claims.append(claim)
    return _reseal(draft), claim.claim_id
