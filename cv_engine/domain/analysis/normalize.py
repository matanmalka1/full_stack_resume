"""Turn one provider reading into an analysis, keeping what survives the checks.

The rule here is the whole change: a proposal is normalized, never refused for
one bad part. Every check the engine can actually perform still runs - a cited
fact must exist and be canonical, a positive reading must have evidence left
after that, a quote must occur in the posting, a canonical boundary still caps
a match - and each one that fails *lowers what the analysis claims* and
records an `AnalysisIssue`. Nothing here raises. A response that cannot be
parsed at all fails earlier, at the provider boundary, which is the one place
failure still means failure.

What that buys is visible in the run that motivated it: sixteen requirements
read correctly used to be discarded because one span reached a character past
its sentence.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import cast

from ..contracts.analysis import JobAnalysis, Language, OverrideKey, Requirement
from ..contracts.analysis_proposal import (
    AnalysisIssue,
    AnalysisProposal,
    Importance,
    ProposedRequirement,
    RequirementSource,
    ShortfallSeverity,
)
from ..facts import FactStore, FactStoreError
from ..profiles import ProfileStore, classification_mismatch
from .requirements.concepts import RequirementConceptStore
from .requirements.evidence import boundary_facts_for_quote
from .requirements.identity import normalize_span, requirement_id

#: The prompt version is recorded with provider provenance and does not determine
#: requirement identity. Only a change to the identity algorithm moves this version.
REQUIREMENT_ID_VERSION = "v1"

#: Least claim first. Merging duplicates and resolving conflicts both take the
#: lowest, because two readings of one sentence that disagree are not evidence
#: for the more flattering one. `unknown` sits below `unsupported` deliberately:
#: "we could not tell" claims less about the candidate than "they lack this".
_COVERAGE_ORDER: tuple[str, ...] = ("unknown", "unsupported", "partial", "matched")
_IMPORTANCE_ORDER: tuple[Importance, ...] = ("unknown", "preferred", "mandatory")


def _classified_values(proposal, profiles: ProfileStore, overrides: Mapping[OverrideKey, str]):
    """Reconcile a proposed classification with the user's overrides.

    Moved here from the old assembly module, which is gone: it was the one part
    of it that survived, and leaving a file behind for one function would have
    kept the old build path looking alive.

    A Profile already owns exactly one Track. Treating both provider fields as
    independent choices makes the provider capable of returning an impossible
    pair even though the Profile is otherwise usable. The Profile therefore
    supplies the Track for an ordinary proposal. An explicit user Track
    override is different: it is a material classification decision, so keep
    it and let the consistency guard refuse a mismatched partial correction
    rather than silently changing what the user chose.
    """
    profile = type(proposal.profile)(overrides.get("profile", proposal.profile.value))
    emphasis = type(proposal.emphasis)(overrides.get("emphasis", proposal.emphasis.value))
    selected = profiles.get(profile)
    track = type(proposal.track)(overrides.get("track", selected.track.value))
    mismatch = classification_mismatch(selected, track, emphasis)
    if mismatch == "track":
        raise ValueError(
            f"classified Track {track.value} and Profile {profile.value} are inconsistent"
        )
    if mismatch == "emphasis":
        raise ValueError(f"Emphasis {emphasis.value} is not allowed for Profile {profile.value}")
    language = overrides.get("language", proposal.language)
    if language not in ("en", "he"):
        raise ValueError(f"unsupported analysis language: {language}")
    return track, profile, emphasis, cast(Language, language)


_WHITESPACE = re.compile(r"\s+")


def _collapsed(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip()


def _merge_key(text: str) -> str:
    return _collapsed(text).casefold()


def locate(quote: str, source_text: str) -> RequirementSource:
    """Where the posting says this, and on what terms the engine found it.

    Four answers, and the difference between them matters downstream. `exact`
    is one occurrence with a span. `normalized` is the posting saying it with
    different whitespace - verified, and not ambiguous about anything.
    `ambiguous` is the posting saying it in several places - also verified,
    because repetition does not make the text less present. `not_found` is the
    only one that is not a verification.

    Only `exact` carries offsets. The other two verified answers deliberately
    do not, which is why the match is stated here rather than inferred later
    from a missing span.
    """
    exact = [index for index in range(len(source_text)) if source_text.startswith(quote, index)]
    if len(exact) == 1:
        return RequirementSource(
            quote=quote, match="exact", start=exact[0], end=exact[0] + len(quote)
        )
    if exact:
        return RequirementSource(quote=quote, match="ambiguous")
    collapsed = _collapsed(quote)
    collapsed_source = _collapsed(source_text)
    if collapsed:
        # Said, but not spelled the same way - a line break where the posting
        # wrapped, or a run of spaces. Counted rather than merely found: a
        # quote that repeats is ambiguous whichever spelling it repeats in, and
        # a containment test would have called the second occurrence a clean
        # single match. No offsets either way, because they would point into a
        # string the snapshot does not hold.
        occurrences = collapsed_source.count(collapsed)
        if occurrences == 1:
            return RequirementSource(quote=quote, match="normalized")
        if occurrences > 1:
            return RequirementSource(quote=quote, match="ambiguous")
    return RequirementSource(quote=quote, match="not_found")


def _merge(first: ProposedRequirement, second: ProposedRequirement) -> ProposedRequirement:
    coverage = min((first.coverage, second.coverage), key=_COVERAGE_ORDER.index)
    # Severity describes the surviving (lower) coverage claim.  A more
    # flattering reading's default ``unknown`` must not erase the explicit
    # severity attached to the reading we actually keep.
    surviving_readings = tuple(
        item for item in (first, second) if item.coverage == coverage
    )
    if coverage == "matched":
        shortfall_severity = "none"
    elif coverage == "unsupported":
        shortfall_severity = "material"
    elif coverage == "unknown" or any(
        item.shortfall_severity == "unknown" for item in surviving_readings
    ):
        shortfall_severity = "unknown"
    else:
        shortfall_severity = (
            "material"
            if any(item.shortfall_severity == "material" for item in surviving_readings)
            else "minor"
        )
    shortfall_reason = next(
        (
            item.shortfall_reason
            for item in (first, second)
            if item.shortfall_severity == shortfall_severity and item.shortfall_reason
        ),
        first.shortfall_reason or second.shortfall_reason,
    )
    return first.model_copy(
        update={
            # Upward, unlike coverage. Coverage is a claim about the
            # candidate, so the lower reading is the safe one; importance is
            # the employer's demand, and taking the lower reading there would
            # quietly relieve the candidate of a requirement the posting
            # stated - lightening the Fit weighting and dissolving hard gaps.
            "importance": max((first.importance, second.importance), key=_IMPORTANCE_ORDER.index),
            "coverage": coverage,
            "shortfall_severity": shortfall_severity,
            "shortfall_reason": shortfall_reason,
            "fact_ids": list(dict.fromkeys([*first.fact_ids, *second.fact_ids])),
        }
    )


def _deduplicate(
    requirements: Sequence[ProposedRequirement],
) -> tuple[list[tuple[int, ProposedRequirement]], list[AnalysisIssue]]:
    """Merge restatements, carrying each survivor's index in the *proposal*.

    `requirement_index` is documented as addressing the proposal the provider
    sent, which is the only list anyone reading the preserved response can look
    at. Re-numbering after the merge would point every later issue at a list
    that exists nowhere outside this function.
    """
    merged: dict[str, tuple[int, ProposedRequirement]] = {}
    issues: list[AnalysisIssue] = []
    for index, proposed in enumerate(requirements):
        key = _merge_key(proposed.text)
        if key in merged:
            first_index, first = merged[key]
            merged[key] = (first_index, _merge(first, proposed))
            issues.append(
                AnalysisIssue(
                    code="duplicate_requirement",
                    requirement_index=index,
                    details={
                        "text": _collapsed(proposed.text)[:120],
                        "merged_into_index": str(first_index),
                    },
                )
            )
            continue
        merged[key] = (index, proposed)
    return list(merged.values()), issues


def _surviving_facts(
    proposed: ProposedRequirement, index: int, facts: FactStore
) -> tuple[list[str], list[AnalysisIssue]]:
    kept: list[str] = []
    issues: list[AnalysisIssue] = []
    for fact_id in dict.fromkeys(proposed.fact_ids):
        try:
            facts.get(fact_id, canonical_only=True)
        except FactStoreError:
            code = "unknown_fact" if fact_id not in facts.facts else "fact_not_canonical"
            issues.append(
                AnalysisIssue(code=code, requirement_index=index, details={"fact_id": fact_id})
            )
            continue
        kept.append(fact_id)
    return kept, issues


def normalize_requirement(
    proposed: ProposedRequirement,
    index: int,
    *,
    source_text: str,
    facts: FactStore,
    concepts: RequirementConceptStore,
    normalized_hash: str,
    ordinal: int = 0,
) -> tuple[Requirement | None, list[AnalysisIssue]]:
    """One proposed requirement, narrowed to what the engine can stand behind.

    The match carries on `Requirement.source` rather than being read back off
    `attestation`: that field holds a single exact span, so a quote the posting
    states in two places, or states with different whitespace, is verified and
    has no span - and inferring the status from the absence counted both as
    unverified.
    """
    issues: list[AnalysisIssue] = []
    text = _collapsed(proposed.text)
    if not text:
        return None, [AnalysisIssue(code="requirement_unusable", requirement_index=index)]

    source = locate(proposed.text, source_text)
    if source.match == "not_found":
        issues.append(
            AnalysisIssue(
                code="quote_not_found", requirement_index=index, details={"text": text[:120]}
            )
        )
    elif source.match == "ambiguous":
        # `normalized` is deliberately not an issue: the posting says exactly
        # this, only wrapped differently, and nothing about it is uncertain.
        issues.append(
            AnalysisIssue(
                code="quote_ambiguous", requirement_index=index, details={"text": text[:120]}
            )
        )

    supporting, fact_issues = _surviving_facts(proposed, index, facts)
    issues += fact_issues

    coverage = proposed.coverage
    shortfall_severity = proposed.shortfall_severity
    shortfall_reason = proposed.shortfall_reason
    if coverage in ("matched", "partial") and not supporting:
        # The reading was positive and nothing canonical was left to show for
        # it. `unknown`, not `unsupported`: the evidence failed, which is not
        # the same as the candidate lacking the thing.
        coverage = "unknown"
        shortfall_severity = "unknown"
        shortfall_reason = "Positive coverage could not be verified from canonical evidence."
        issues.append(AnalysisIssue(code="coverage_without_evidence", requirement_index=index))

    boundaries = boundary_facts_for_quote(proposed.text, concepts, facts)
    if boundaries and coverage == "matched":
        # A canonical boundary fact is the candidate's own statement that this
        # is not verified. It caps a match and never lifts one.
        coverage = "partial"
        shortfall_severity = "material"

    expected_severities: dict[str, ShortfallSeverity] = {
        "matched": "none",
        "unsupported": "material",
        "unknown": "unknown",
    }
    expected_severity = expected_severities.get(coverage)
    if expected_severity is not None and shortfall_severity != expected_severity:
        shortfall_severity = expected_severity
        issues.append(AnalysisIssue(code="shortfall_inconsistent", requirement_index=index))
    elif coverage == "partial" and shortfall_severity == "none":
        shortfall_severity = "unknown"
        issues.append(AnalysisIssue(code="shortfall_inconsistent", requirement_index=index))
    elif (
        coverage == "partial"
        and shortfall_severity in ("minor", "material")
        and not boundaries
        and not (shortfall_reason or "").strip()
    ):
        shortfall_severity = "unknown"
        issues.append(AnalysisIssue(code="shortfall_inconsistent", requirement_index=index))
    if coverage == "matched":
        shortfall_reason = None

    requirement = Requirement(
        requirement_id=requirement_id(
            normalized_hash=normalized_hash,
            # The posting and the requirement's own words, plus the version of
            # this algorithm. Nothing about who read it or how they were asked.
            identity_version=REQUIREMENT_ID_VERSION,
            identity_span=normalize_span(text),
            ordinal=ordinal,
        ),
        text=text,
        importance=proposed.importance,
        coverage=coverage,
        shortfall_severity=shortfall_severity,
        shortfall_reason=shortfall_reason,
        supporting_fact_ids=supporting,
        boundary_fact_ids=boundaries,
        source=source,
    )
    return requirement, issues


def normalize_analysis_proposal(
    proposal: AnalysisProposal,
    *,
    source_text: str,
    facts: FactStore,
    profiles: ProfileStore,
    concepts: RequirementConceptStore,
    normalized_hash: str,
    overrides: Mapping[OverrideKey, str] | None = None,
) -> JobAnalysis:
    """One provider reading, normalized into an analysis and what it cost.

    The issues travel on the analysis, not beside it. They are its own account
    of where it was narrowed - a citation dropped, a coverage lowered, a quote
    the posting does not carry - and that account is what a user needs when the
    analysis claims less than the posting appears to ask for. Returned in
    memory and left out of the record, it would be gone by the time anyone
    asked.

    They are warnings: none of them stops the workflow, because none of them is
    a reason to disbelieve the rest of the reading. What still stops the
    workflow lives where it belongs - an unsupported claim reaching a draft.
    """
    deduplicated, issues = _deduplicate(proposal.requirements)

    requirements: list[Requirement] = []
    for index, proposed in deduplicated:
        normalized, requirement_issues = normalize_requirement(
            proposed,
            index,
            source_text=source_text,
            facts=facts,
            concepts=concepts,
            normalized_hash=normalized_hash,
        )
        issues += requirement_issues
        if normalized is not None:
            requirements.append(normalized)

    verified = sum(
        1
        for requirement in requirements
        if requirement.source is not None and requirement.source.verified
    )
    # Reuses the one resolver that derives the provider's Track from its
    # Profile, reconciles explicit user overrides, and refuses an Emphasis (or
    # user-overridden Track) the Profile does not allow.
    track, profile, emphasis, language = _classified_values(
        proposal, profiles, dict(overrides or {})
    )
    analysis = JobAnalysis(
        track=track,
        profile=profile,
        emphasis=emphasis,
        language=language,
        summary=proposal.summary,
        keywords=sorted(set(proposal.keywords)),
        requirements=requirements,
        issues=issues,
        source_coverage=(verified / len(requirements)) if requirements else None,
        user_override=dict(overrides or {}),
    )
    return analysis
