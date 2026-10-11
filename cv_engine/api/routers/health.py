from __future__ import annotations

from fastapi import APIRouter

from ...application.errors import KnowledgeRejected
from ..dependencies import Services
from ..schemas.health import HealthResponse, KnowledgeVersions

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Instance identity and versions")
def health(services: Services) -> HealthResponse:
    """The instance answers whether or not anyone has Knowledge yet.

    Knowledge is a user's rows, so an installation with no user, or one not yet
    imported, is healthy and reports no Knowledge versions rather than failing.
    """
    try:
        versions = services.knowledge_queries.knowledge_versions()
    except KnowledgeRejected:
        knowledge = None
    else:
        knowledge = KnowledgeVersions(
            facts=versions.facts,
            facts_lifecycle=versions.facts_lifecycle,
            profiles=versions.profiles,
            emphasis_policies=versions.emphasis_policies,
            presentations=versions.presentations,
            candidate_context=versions.candidate_context,
            requirement_concepts=versions.requirement_concepts,
        )
    identity = services.identity
    return HealthResponse(
        status="ok",
        product_version=identity.product_version,
        api_version=identity.api_version,
        schema_version=identity.schema_version,
        knowledge=knowledge,
    )
