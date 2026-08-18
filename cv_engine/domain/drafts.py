from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass

from .facts import FactStore
from .draft_markdown import serialize_markdown as _serialize_markdown
from .models import (
    CandidateContext,
    ClaimLine,
    DraftDocument,
    JobAnalysis,
    OmissionReason,
    Profile,
    ResumeSection,
    SelectionManifest,
)
from .presentations import PresentationStore, PresentedClaim
from .selection import EmphasisPolicyStore, build_selection
from ..util import canonical_json, sha256_text


CLAIM_NAMESPACE = uuid.UUID("e47cfc95-7f5c-4dd2-acd4-19be02c8f988")
CANONICAL_JOIN_TEMPLATE = ("canonical-renderings", "1.0.0")
EXTRACTIVE_DERIVATION = ("extractive-clauses", "1.0.0")
EDITABLE_STYLES = frozenset({"paragraph", "bullet", "item"})


@dataclass(frozen=True)
class CompositeTemplate:
    template_id: str
    version: str
    input_styles: frozenset[str]
    output_styles: frozenset[str]


COMPOSITE_TEMPLATES = {
    CANONICAL_JOIN_TEMPLATE: CompositeTemplate(
        template_id=CANONICAL_JOIN_TEMPLATE[0],
        version=CANONICAL_JOIN_TEMPLATE[1],
        input_styles=EDITABLE_STYLES,
        output_styles=EDITABLE_STYLES,
    ),
}


def _claim(
    style: str,
    text: str,
    fact_ids: list[str],
    claim_type: str = "canonical",
    *,
    template_id: str | None = None,
    template_version: str | None = None,
    derivation_id: str | None = None,
    derivation_version: str | None = None,
    pending_reason: str | None = None,
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
    )


def _omitted_facts(
    facts: FactStore,
    selection: SelectionManifest,
    selected: set[str],
) -> dict[str, OmissionReason]:
    """Why each unused canonical fact is absent, in codes rather than prose.

    A fact the Profile never offered is a different situation from one that
    competed and lost, and both are different from one evicted to restore a
    required tag. Callers and tests can tell them apart.
    """
    considered: dict[str, OmissionReason] = {
        candidate.fact_id: candidate.reason
        for candidate in selection.candidates
        if candidate.reason is not None
    }
    return {
        fact_id: considered.get(fact_id, "not_in_profile_pool")
        for fact_id in sorted(set(facts.facts) - selected)
    }


def build_draft(
    *,
    application_id: str,
    job_snapshot_id: str,
    job_analysis_id: str,
    analysis: JobAnalysis,
    profile: Profile,
    facts: FactStore,
    policies: EmphasisPolicyStore,
    candidate: CandidateContext,
    presentations: PresentationStore | None = None,
    selection: SelectionManifest | None = None,
) -> DraftDocument:
    if analysis.profile is not profile.profile or analysis.track is not profile.track:
        raise ValueError("analysis and profile do not match")
    if analysis.emphasis not in profile.allowed_emphases:
        raise ValueError(f"emphasis {analysis.emphasis} is not allowed for {profile.profile}")

    language = analysis.language
    contact_ids = candidate.contacts_for_track(analysis.track.value)
    contacts = [
        _claim("contact", facts.rendering(fact_id, language), [fact_id]) for fact_id in contact_ids
    ]

    if selection is None:
        selected_by_section, selection = build_selection(
            analysis=analysis,
            profile=profile,
            policy=policies.get(analysis.emphasis),
            policy_store_version=policies.version,
            facts=facts,
            line_groups=(
                presentations.line_groups(profile, analysis.emphasis)
                if presentations is not None
                else None
            ),
        )
    else:
        if selection.emphasis is not analysis.emphasis:
            raise ValueError("selection plan emphasis does not match analysis")
        selected = set(selection.selected_fact_ids)
        selected_by_section = {
            spec.name_en: [fact_id for fact_id in spec.fact_ids if fact_id in selected]
            for spec in profile.sections
        }

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
                emphasis=analysis.emphasis,
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
        emphasis=analysis.emphasis,
        name=candidate.display_name(language),
        headline=headline,
        contacts=contacts,
        sections=sections,
        selected_fact_ids=sorted(selected),
        omitted_facts=_omitted_facts(facts, selection, selected),
        selection=selection,
        fact_store_version=facts.version,
    )
    markdown = _serialize_markdown(draft)
    return draft.model_copy(update={"content_hash": sha256_text(markdown)})


def seal_draft(draft: DraftDocument) -> tuple[DraftDocument, str, str]:
    """The two payloads a stored draft consists of, and the draft they describe.

    The content hash is bound to the Markdown here, so the pair cannot be
    written out of step. Where the two payloads land is a storage decision made
    outside this layer.
    """
    markdown = _serialize_markdown(draft)
    sealed = draft.model_copy(update={"content_hash": sha256_text(markdown)})
    manifest = json.dumps(sealed.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
    return sealed, markdown, manifest


def _claims(draft: DraftDocument) -> list[ClaimLine]:
    return [
        draft.headline,
        *draft.contacts,
        *(claim for section in draft.sections for claim in section.claims),
    ]


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


def _refresh_selection(draft: DraftDocument, facts: FactStore) -> DraftDocument:
    selected = {fact_id for claim in _claims(draft) for fact_id in claim.fact_ids}
    draft.selected_fact_ids = sorted(selected)
    if draft.selection is not None:
        # A manual edit may relink a claim to a different fact in the pool. The
        # engine's decision record is not rewritten to match: it is flagged, so
        # the audit trail keeps saying what the policy actually chose.
        body = {
            fact_id
            for section in draft.sections
            for claim in section.claims
            for fact_id in claim.fact_ids
        }
        if body != set(draft.selection.selected_fact_ids):
            draft.selection = draft.selection.model_copy(update={"superseded_by_manual_edit": True})
    draft.omitted_facts = _omitted_facts(
        facts,
        draft.selection
        or SelectionManifest(
            policy_version="",
            emphasis=draft.emphasis,
            emphasis_policy_version="",
        ),
        selected,
    )
    return draft.model_copy(update={"content_hash": sha256_text(_serialize_markdown(draft))})


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
    try:
        current = next(claim for claim in _claims(draft) if claim.claim_id == claim_id)
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
        if len(fact_ids) == 1:
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
    return _refresh_selection(draft, facts)


def register_linked_claim(
    draft: DraftDocument,
    claim_id: str,
    new_text: str,
    fact_ids: list[str],
    facts: FactStore,
) -> DraftDocument:
    return apply_claim_edit(draft, claim_id, fact_ids, facts, text=new_text)


def register_composite_claim(
    draft: DraftDocument,
    claim_id: str,
    fact_ids: list[str],
    facts: FactStore,
    *,
    template_id: str = CANONICAL_JOIN_TEMPLATE[0],
    template_version: str = CANONICAL_JOIN_TEMPLATE[1],
) -> DraftDocument:
    return apply_claim_edit(
        draft,
        claim_id,
        fact_ids,
        facts,
        template_id=template_id,
        template_version=template_version,
    )
