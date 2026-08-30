"""The fact lifecycle over HTTP.

`FactResponse` restates the domain `Fact` rather than carrying it, which is the
opposite of how the analysis schemas treat `JobAnalysis`. The reason is one
field: a stored `Fact` carries `source_file`, a repository-relative path like
`base/sales.md`, and architecture 14 forbids an endpoint from exposing a
filesystem location. What a client needs is *which* canonical source a fact
belongs to, so the wire carries `source` - the name alone, derived through
`source_name_of`.

Two constraints are named here rather than left to the application layer,
because refusing them at the transport boundary is a `422` with a field name
instead of a `412` after a command has been built. The fact *source* is a
closed set of four files, and a promotion requires `confirm: true` - the
explicit confirmation the specification requires for a status change, which
must fail rather than be interpreted when it is absent.

Fact identity is deliberately absent from every request. Identity is generated
(product-spec.md 561: "The UI does not expose fact-ID creation"), and the
application layer refuses a caller-supplied one; not accepting the field is
how this layer states the same rule.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ...application.commands import FactEventView
from ...domain.facts import FACT_SOURCE_NAMES, source_name_of
from ...domain.models import Fact, FactStatus, SelectionPlan
from .health import HttpSchema

FactSource = Literal["common.md", "sales.md", "development.md", "situational_skills.md"]

# The transport vocabulary is the domain's, derived rather than retyped: a
# fifth source file added to `FACT_SOURCE_NAMES` must not silently keep being
# refused here as an unknown value. Raised rather than asserted, because
# `python -O` strips an assert and a guard that can vanish is not a guard.
if set(FactSource.__args__) != set(FACT_SOURCE_NAMES):
    raise RuntimeError(
        "FactSource must match domain.facts.FACT_SOURCE_NAMES: "
        f"{sorted(set(FACT_SOURCE_NAMES) ^ set(FactSource.__args__))} differ"
    )


#: The lifecycle statuses a client may filter a fact listing by. Re-exported
#: from the schemas package so routers name transport types only: a router that
#: imports a domain type is building, inspecting, or serialising a domain object,
#: which is how business logic arrives in a router.
FactStatusFilter = FactStatus


class FactResponse(HttpSchema):
    """One fact as a client sees it: its content, without where it is stored."""

    fact_id: str
    meaning: str
    renderings: dict[str, str]
    tags: list[str]
    status: FactStatus
    provenance: str
    source: str
    resume_style: str
    confirmed_at: str | None = None
    effective_dates: str | None = None
    replaces: str | None = None
    link_target: str | None = None

    @classmethod
    def of(cls, fact: Fact) -> FactResponse:
        """Project one stored fact onto the wire, naming its source not its path."""
        return cls.model_validate(
            {
                **fact.model_dump(mode="json", exclude={"source_file"}),
                "source": source_name_of(fact),
            }
        )


class FactEventResponse(HttpSchema):
    """One entry of the immutable fact lifecycle trail."""

    id: str
    fact_id: str
    source: str
    event_type: str
    from_status: str | None
    to_status: str
    application_id: str | None
    claim_id: str | None
    reason: str
    fact_hash: str
    facts_version: str
    lifecycle_version: str
    created_at: str


class FactListItemResponse(HttpSchema):
    """One fact, beside the status its audit trail last recorded.

    `recorded_status` is `null` for a fact the trail never saw, which is what
    reconciliation exists to notice; it is not the same as the fact's status.
    """

    fact: FactResponse
    recorded_status: str | None = None


class FactListResponse(HttpSchema):
    items: list[FactListItemResponse]


class FactDetailResponse(HttpSchema):
    fact: FactResponse
    events: list[FactEventResponse]


class FactHistoryResponse(HttpSchema):
    events: list[FactEventResponse]


class FactMutationResponse(HttpSchema):
    """One fact after a lifecycle write, with the versions that write produced."""

    fact: FactResponse
    event_id: str
    facts_version: str
    lifecycle_version: str


class FactAttachmentResponse(FactMutationResponse):
    """Where the fact was offered, not where that Profile is stored.

    The application result also carries `profile_source`, the Profile
    document's repository-relative path. `profile` and `section` already say
    which pool the fact joined, so the location is dropped here rather than
    published: architecture 14 forbids an endpoint exposing a stored path, and
    that rule is about the value, not about whether its field name happens to
    match the guard's pattern.
    """

    profile: str
    section: str
    pinned: bool
    profile_store_version: str


class ConfirmAndUseFactResponse(HttpSchema):
    """The one logical command's whole outcome: promoted, attached, selected."""

    fact: FactResponse
    event_ids: list[str]
    selection_plan: SelectionPlan
    facts_version: str
    lifecycle_version: str
    profile_store_version: str


class FactContentRequest(HttpSchema):
    """What a new fact says. Identity is generated, so it is not accepted here.

    `renderings` is the language-keyed display text; English is required by the
    domain model. Meaning, tags, and provenance require explicit input and are
    never inferred or AI-written.
    """

    source: FactSource
    meaning: str = Field(min_length=1)
    renderings: dict[str, str]
    tags: list[str] = Field(min_length=1)
    provenance: str = Field(min_length=1)
    resume_style: Literal["paragraph", "heading", "date", "bullet", "item", "contact"]
    effective_dates: str | None = None
    replaces: str | None = None
    reason: str = ""


class CaptureClaimFactRequest(HttpSchema):
    """A fact created from an unsupported manual claim in a working draft.

    The claim's exact text is copied without AI rewriting, so `renderings` is
    absent: the English rendering comes from the claim itself. Everything the
    claim cannot supply - meaning, tags, provenance - is explicit input.
    """

    application_id: str
    claim_id: str
    source: FactSource
    meaning: str = Field(min_length=1)
    tags: list[str] = Field(min_length=1)
    english: str | None = None
    hebrew: str | None = None
    provenance: str | None = None
    effective_dates: str | None = None
    replaces: str | None = None
    reason: str = ""


class FactTransitionRequest(HttpSchema):
    """A promotion along `pending -> confirmed -> canonical`.

    `confirm` is the explicit confirmation the specification requires for a
    status change. It defaults to `false` so that omitting it refuses the
    transition rather than performing it.
    """

    confirm: bool = False
    reason: str = ""


class AttachFactRequest(HttpSchema):
    """Offer one canonical fact to a Profile section's candidate pool."""

    profile: str
    section: str
    pin: bool = False


class ConfirmAndUseFactRequest(HttpSchema):
    """Promote, attach, and select one fact as a single recoverable command."""

    application_id: str
    job_analysis_id: str
    profile: str
    section: str
    reason: str = ""


class FactStatusQuery(HttpSchema):
    status: FactStatus | None = None


def fact_event_response(event: FactEventView) -> FactEventResponse:
    """Project one audit row onto the wire, naming its source not its path."""
    return FactEventResponse.model_validate(
        {
            **event.model_dump(mode="json", exclude={"source_file"}),
            "source": event.source_file.rsplit("/", 1)[-1],
        }
    )
