"""The one place that decides whether a draft's provenance chain holds.

`application -> job snapshot -> job analysis -> draft` is a single chain, not
four independent lookups. Resolving each link separately by recency is what lets
a draft be built from one snapshot and validated against an analysis of another,
or approved against whichever analysis happens to be newest. Every gate that
consumes a draft -- validation, approval, rendering, and the ready recheck --
goes through `check_draft_chain` so they cannot drift apart from each other.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.contracts.analysis import JobAnalysis
from ..domain.contracts.drafts import DraftDocument
from ..domain.contracts.selection import SelectionPlan
from ..domain.facts import FactStore
from ..domain.profiles import ProfileStore
from ..util import canonical_json, sha256_text
from .errors import UnknownRecord
from .ports import DraftRepository

# What a re-analysis may change without invalidating a draft built from an
# earlier one. Everything else -- Track, Profile, Emphasis, language, keywords,
# requirements, and user overrides -- either changes what
# the document selects and says or changes a gate it had to pass, so a later
# analysis that differs there supersedes the draft rather than re-describing it.
IMMATERIAL_ANALYSIS_FIELDS = frozenset(
    {
        # An account of where the reading was narrowed, and a measurement of how
        # much of it the engine anchored in the posting. Neither changes what
        # the document selects or says: a re-run that reads the same
        # requirements the same way, and happens to record one more dropped
        # citation, has not superseded a draft built from the first one. What
        # those issues were *about* - a coverage lowered, a fact removed - is
        # already in `requirements`, which stays material.
        "issues",
        "source_coverage",
    }
)


def material_analysis_key(analysis: JobAnalysis) -> str:
    return sha256_text(
        canonical_json(
            {
                key: value
                for key, value in analysis.model_dump(mode="json").items()
                if key not in IMMATERIAL_ANALYSIS_FIELDS
            }
        )
    )


class ChainError(ValueError):
    pass


def draft_source_mismatch(
    application_id: str,
    analysis_id: str,
    analysis_record: dict,
    plan: SelectionPlan,
) -> str | None:
    """Return the invalid link in a named draft source pair, if any."""
    if analysis_record["application_id"] != application_id:
        return "analysis"
    if plan.application_id != application_id or plan.job_analysis_id != analysis_id:
        return "selection_plan"
    return None


@dataclass(frozen=True)
class DraftChain:
    """A resolved chain, or the reasons it does not resolve."""

    application_id: str
    job_snapshot_id: str
    job_analysis_id: str | None
    analysis: JobAnalysis | None
    problems: list[tuple[str, str]]

    @property
    def valid(self) -> bool:
        return not self.problems

    def bound(self) -> tuple[str, JobAnalysis]:
        """The exact analysis this draft was built from, or a refusal."""
        if not self.valid or self.job_analysis_id is None or self.analysis is None:
            raise ChainError(self.describe())
        return self.job_analysis_id, self.analysis

    def describe(self) -> str:
        return "; ".join(f"{code}: {message}" for code, message in self.problems)


@dataclass(frozen=True)
class DraftChainSources:
    """Only the persisted links and recency evidence the draft chain consumes."""

    analysis_record: dict | None
    snapshot_record: dict | None
    latest_snapshot_id: str | None
    analyses: tuple[dict, ...]


def check_draft_chain(
    repo: DraftRepository,
    application_id: str,
    draft: DraftDocument,
    profiles: ProfileStore,
    facts: FactStore,
    *,
    recorded_analysis_id: str | None = None,
) -> DraftChain:
    """Legacy consumers load the same inputs used by token-scoped draft consumers."""
    record = None
    snapshot = None
    latest_snapshot_id = None
    history = ()
    analysis_id = draft.job_analysis_id or recorded_analysis_id
    if draft.application_id == application_id and analysis_id is not None:
        try:
            record = repo.get_analysis(analysis_id)
        except UnknownRecord:
            pass
        if record is not None:
            try:
                snapshot = repo.get_snapshot(draft.job_snapshot_id)
            except UnknownRecord:
                pass
            if record["application_id"] == application_id:
                try:
                    latest_snapshot_id = repo.latest_snapshot(application_id)["id"]
                except UnknownRecord:
                    pass
                history = tuple(repo.analyses(application_id))
    return check_loaded_draft_chain(
        DraftChainSources(record, snapshot, latest_snapshot_id, history),
        application_id,
        draft,
        profiles,
        facts,
        recorded_analysis_id=recorded_analysis_id,
    )


def check_loaded_draft_chain(
    sources: DraftChainSources,
    application_id: str,
    draft: DraftDocument,
    profiles: ProfileStore,
    facts: FactStore,
    *,
    recorded_analysis_id: str | None = None,
) -> DraftChain:
    """Verify a draft's chain against the database as it stands right now.

    `recorded_analysis_id` is the binding held by an approved version's own
    immutable decision record. It is used only for pre-binding "1.0" manifests,
    which predate `job_analysis_id`; a draft that carries its own binding always
    wins, so a decision record can never re-point a draft at another analysis.
    """
    problems: list[tuple[str, str]] = []

    def unresolved(
        *, analysis_id: str | None = None, analysis: JobAnalysis | None = None
    ) -> DraftChain:
        return DraftChain(application_id, draft.job_snapshot_id, analysis_id, analysis, problems)

    # Ownership first: every check below is about this application's records, so
    # a foreign draft must not be measured against them at all.
    if draft.application_id != application_id:
        problems.append(
            (
                "draft-application-mismatch",
                f"the draft belongs to application {draft.application_id}, not {application_id}",
            )
        )
        return unresolved()

    analysis_id = draft.job_analysis_id or recorded_analysis_id
    if analysis_id is None:
        problems.append(
            (
                "unbound-draft-analysis",
                "the draft names no job analysis and no decision record binds one; re-create the draft",
            )
        )
        return unresolved()

    try:
        record = sources.analysis_record
        if record is None:
            raise UnknownRecord(analysis_id)
    except UnknownRecord:
        problems.append(("unknown-job-analysis", f"no job analysis {analysis_id} exists"))
        return unresolved(analysis_id=analysis_id)

    analysis: JobAnalysis = record["analysis"]
    owned = record["application_id"] == application_id
    if not owned:
        problems.append(
            (
                "analysis-application-mismatch",
                f"job analysis {analysis_id} belongs to application {record['application_id']}",
            )
        )
    if record["job_snapshot_id"] != draft.job_snapshot_id:
        problems.append(
            (
                "analysis-snapshot-mismatch",
                f"the bound analysis was made from job snapshot {record['job_snapshot_id']}, "
                f"but the draft names {draft.job_snapshot_id}",
            )
        )

    try:
        snapshot = sources.snapshot_record
        if snapshot is None:
            raise UnknownRecord(draft.job_snapshot_id)
    except UnknownRecord:
        problems.append(("unknown-job-snapshot", f"no job snapshot {draft.job_snapshot_id} exists"))
    else:
        if snapshot["application_id"] != application_id:
            problems.append(
                (
                    "snapshot-application-mismatch",
                    f"job snapshot {draft.job_snapshot_id} belongs to application "
                    f"{snapshot['application_id']}",
                )
            )

    expected_emphasis = (
        draft.selection.emphasis if draft.selection is not None else analysis.emphasis
    )
    drifted = [
        f"{name}: draft {left} vs analysis {right}"
        for name, left, right in (
            ("track", draft.track.value, analysis.track.value),
            ("profile", draft.profile.value, analysis.profile.value),
            ("emphasis", draft.emphasis.value, expected_emphasis.value),
            ("language", draft.language, analysis.language),
        )
        if left != right
    ]
    if drifted:
        problems.append(("draft-analysis-classification-mismatch", "; ".join(drifted)))

    profile = profiles.get(draft.profile)
    if profile.track is not draft.track:
        problems.append(
            (
                "track-profile-mismatch",
                f"Profile {draft.profile.value} belongs to Track {profile.track.value}, "
                f"not {draft.track.value}",
            )
        )
    if draft.emphasis not in profile.allowed_emphases:
        problems.append(
            (
                "emphasis-not-allowed",
                f"{draft.emphasis.value} is not an allowed Emphasis for {draft.profile.value}",
            )
        )
    if draft.fact_store_version != facts.version:
        problems.append(
            (
                "fact-store-version-mismatch",
                "the draft was built from a different fact-store version",
            )
        )

    if owned:
        problems.extend(_loaded_staleness(sources, record, analysis))
    return DraftChain(application_id, draft.job_snapshot_id, analysis_id, analysis, problems)


def _loaded_staleness(
    sources: DraftChainSources,
    record: dict,
    analysis: JobAnalysis,
) -> list[tuple[str, str]]:
    """Whether the job moved on after the bound analysis was made.

    A new job snapshot is new job text, so it always requires a fresh analysis
    before anything is drafted from it. A newer analysis of the same snapshot
    only supersedes the draft when it says something materially different --
    re-running the classifier and getting the same answer is not a change.
    """
    problems: list[tuple[str, str]] = []
    if sources.latest_snapshot_id is None:
        raise UnknownRecord(f"no snapshot for application {record['application_id']}")
    if sources.latest_snapshot_id != record["job_snapshot_id"]:
        problems.append(
            (
                "new-snapshot-requires-analysis",
                "a newer job snapshot exists; analyze it before drafting against it",
            )
        )
    bound_key = material_analysis_key(analysis)
    superseding = [
        row
        for row in sources.analyses
        if row["version_number"] > record["version_number"]
        and material_analysis_key(row["analysis"]) != bound_key
    ]
    if superseding:
        problems.append(
            (
                "superseded-by-newer-analysis",
                f"job analysis {superseding[-1]['id']} materially supersedes the analysis "
                "this draft was built from",
            )
        )
    return problems
