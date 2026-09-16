"""Backward-compatible import surface for serialized domain contracts.

New production code should import from the bounded-context modules in
:mod:`cv_engine.domain.contracts`. This module deliberately contains no model
definitions; it preserves the historical import path for external callers and
older tests without recreating the former God Module.
"""

from .contracts.analysis import (
    Coverage,
    FitLevel,
    JobAnalysis,
    Language,
    OverrideKey,
    Requirement,
)
from .contracts.base import StrictModel
from .contracts.drafts import (
    ClaimLine,
    ClaimStyle,
    ClaimType,
    DraftDocument,
    ResumeSection,
    WorkingDraft,
)
from .contracts.knowledge import (
    CandidateContext,
    ContactScheme,
    EmphasisPolicy,
    Fact,
    FactSource,
    FactStatus,
    Profile,
    ResumeSectionSpec,
)
from .contracts.providers import (
    ClaimProposal,
    DraftProposal,
    ProposedClaim,
    ProviderContext,
    ProviderCost,
    ProviderPricing,
    ProviderTaskResult,
    ProviderUsage,
    SectionProposal,
    SelectionProposal,
)
from .contracts.records import (
    ApprovedRevision,
    AuditRecord,
    DecisionRecord,
    ValidationRunLineage,
)
from .contracts.recruitment import ApplicationStatus, TerminalOutcome
from .contracts.selection import (
    OmissionReason,
    SelectionCandidate,
    SelectionManifest,
    SelectionOutcome,
    SelectionPlan,
)
from .contracts.taxonomy import Emphasis, ProfileName, Track
from .contracts.validation import (
    ReadyQualification,
    ValidationIssue,
    ValidationReport,
)

__all__ = [
    "ApplicationStatus",
    "ApprovedRevision",
    "AuditRecord",
    "CandidateContext",
    "ClaimLine",
    "ClaimProposal",
    "ClaimStyle",
    "ClaimType",
    "ContactScheme",
    "Coverage",
    "DecisionRecord",
    "DraftDocument",
    "DraftProposal",
    "Emphasis",
    "EmphasisPolicy",
    "Fact",
    "FactSource",
    "FactStatus",
    "FitLevel",
    "JobAnalysis",
    "Language",
    "OmissionReason",
    "OverrideKey",
    "Profile",
    "ProfileName",
    "ProposedClaim",
    "ProviderContext",
    "ProviderCost",
    "ProviderPricing",
    "ProviderTaskResult",
    "ProviderUsage",
    "ReadyQualification",
    "Requirement",
    "ResumeSection",
    "ResumeSectionSpec",
    "SectionProposal",
    "SelectionCandidate",
    "SelectionManifest",
    "SelectionOutcome",
    "SelectionPlan",
    "SelectionProposal",
    "StrictModel",
    "TerminalOutcome",
    "Track",
    "ValidationIssue",
    "ValidationReport",
    "ValidationRunLineage",
    "WorkingDraft",
]
