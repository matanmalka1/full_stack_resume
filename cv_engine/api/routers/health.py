from __future__ import annotations

from fastapi import APIRouter

from ..dependencies import Services
from ..schemas.health import HealthResponse, KnowledgeVersions

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Instance identity and versions")
def health(services: Services) -> HealthResponse:
    versions = services.knowledge.knowledge_versions()
    identity = services.identity
    return HealthResponse(
        status="ok",
        product_version=identity.product_version,
        api_version=identity.api_version,
        schema_version=identity.schema_version,
        knowledge=KnowledgeVersions(
            facts=versions.facts,
            facts_lifecycle=versions.facts_lifecycle,
            profiles=versions.profiles,
            emphasis_policies=versions.emphasis_policies,
            presentations=versions.presentations,
            candidate_context=versions.candidate_context,
        ),
    )
