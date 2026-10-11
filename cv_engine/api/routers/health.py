from __future__ import annotations

from fastapi import APIRouter

from ..dependencies import Services
from ..schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Instance identity and versions")
def health(services: Services) -> HealthResponse:
    """Instance identity and versions. Anonymous, so it names no user's Knowledge."""
    identity = services.identity
    return HealthResponse(
        status="ok",
        product_version=identity.product_version,
        api_version=identity.api_version,
        schema_version=identity.schema_version,
    )
