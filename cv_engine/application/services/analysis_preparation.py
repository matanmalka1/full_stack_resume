"""Values produced during analysis execution and consumed during activation."""

from __future__ import annotations

from dataclasses import dataclass

from ...domain.contracts.analysis import JobAnalysis
from ...domain.contracts.selection import SelectionManifest
from .proposals import ProviderEvidence


@dataclass(frozen=True)
class PreparedAnalysis:
    result: JobAnalysis
    plan_manifest: SelectionManifest
    provider: str
    model: str
    candidate_context_version: str
    candidate_context_hash: str
    profile_version: str
    selection_policy_version: str
    track_emphasis_dependencies: dict[str, str]
    normalized_role: str
    evidence: ProviderEvidence | None = None
    extraction_evidence: ProviderEvidence | None = None
