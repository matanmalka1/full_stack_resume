"""Assemble and revise analyses from verified AI output."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast

from ..contracts.analysis import (
    JobAnalysis,
    JobClassificationProposal,
    Language,
    OverrideKey,
    Requirement,
    UnderstandingSources,
    UnmappedStatement,
)
from ..facts import FactStore
from ..profiles import ProfileStore, classification_mismatch
from .gaps import (
    fit_level_from_score,
    fit_score_for,
    gaps_from_requirements,
    has_undetermined_mandatory,
)


def _classified_values(proposal, profiles: ProfileStore, overrides: Mapping[OverrideKey, str]):
    profile = type(proposal.profile)(overrides.get("profile", proposal.profile.value))
    track = type(proposal.track)(overrides.get("track", proposal.track.value))
    emphasis = type(proposal.emphasis)(overrides.get("emphasis", proposal.emphasis.value))
    selected = profiles.get(profile)
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


def _analysis_reasons(
    requirements: Sequence[Requirement],
    *,
    extraction_failed: bool,
    requirements_absent: bool,
    requirements_unmapped: bool,
) -> list[str]:
    return list(
        dict.fromkeys(
            [
                *(["extraction-failed"] if extraction_failed else []),
                *(["requirements-absent"] if requirements_absent else []),
                *(["requirements-unmapped"] if requirements_unmapped else []),
                *(["coverage-undetermined"] if has_undetermined_mandatory(requirements) else []),
            ]
        )
    )


def build_analysis(
    *,
    requirements: Sequence[Requirement],
    extraction_version: str,
    extraction_failed: bool,
    requirements_absent: bool,
    requirements_unmapped: bool,
    proposal: JobClassificationProposal,
    profiles: ProfileStore,
    facts: FactStore,
    unmapped_statements: Sequence[UnmappedStatement],
    understanding: UnderstandingSources,
    overrides: Mapping[OverrideKey, str] | None = None,
) -> JobAnalysis:
    """Build an analysis directly; no rules-based shadow analysis is created."""
    applied = dict(overrides or {})
    track, profile, emphasis, language = _classified_values(proposal, profiles, applied)
    requirement_list = list(requirements)
    gaps = gaps_from_requirements(requirement_list, facts)
    fit_score = fit_score_for(
        requirement_list,
        extraction_failed=extraction_failed,
        requirements_absent=requirements_absent,
    )
    reasons = _analysis_reasons(
        requirement_list,
        extraction_failed=extraction_failed,
        requirements_absent=requirements_absent,
        requirements_unmapped=requirements_unmapped,
    )
    return JobAnalysis(
        analysis_version="2.0",
        track=track,
        profile=profile,
        emphasis=emphasis,
        confidence=proposal.confidence,
        rationale=proposal.rationale,
        fit=fit_level_from_score(fit_score, gaps),
        fit_score=fit_score,
        gaps=gaps,
        requirements=requirement_list,
        extraction_version=extraction_version,
        unmapped_statements=list(unmapped_statements),
        understanding=understanding,
        interpretation_decisions=[],
        mandatory_requirements=[g.requirement for g in gaps if g.severity == "hard"],
        preferred_requirements=[g.requirement for g in gaps if g.severity == "warning"],
        keywords=sorted(set(proposal.keywords)),
        language=language,
        approval_reasons=reasons,
        user_override=applied,
    )


def rebase_requirements(
    analysis: JobAnalysis,
    *,
    requirements: Sequence[Requirement],
    extraction_version: str,
    facts: FactStore,
    extraction_failed: bool,
    requirements_absent: bool,
    requirements_unmapped: bool,
) -> JobAnalysis:
    """Recompute derived fields after a user corrects requirement meaning."""
    requirement_list = list(requirements)
    gaps = gaps_from_requirements(requirement_list, facts)
    fit_score = fit_score_for(
        requirement_list,
        extraction_failed=extraction_failed,
        requirements_absent=requirements_absent,
    )
    retained = [
        reason
        for reason in analysis.approval_reasons
        if reason
        not in {
            "extraction-failed",
            "requirements-absent",
            "requirements-unmapped",
            "coverage-undetermined",
        }
    ]
    derived = _analysis_reasons(
        requirement_list,
        extraction_failed=extraction_failed,
        requirements_absent=requirements_absent,
        requirements_unmapped=requirements_unmapped,
    )
    reasons = list(dict.fromkeys([*retained, *derived]))
    return analysis.model_copy(
        update={
            "requirements": requirement_list,
            "extraction_version": extraction_version,
            "gaps": gaps,
            "fit": fit_level_from_score(fit_score, gaps),
            "fit_score": fit_score,
            "mandatory_requirements": [g.requirement for g in gaps if g.severity == "hard"],
            "preferred_requirements": [g.requirement for g in gaps if g.severity == "warning"],
            "approval_reasons": reasons,
        }
    )
