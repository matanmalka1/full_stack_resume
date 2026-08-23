"""The artifact surface: metadata by ID, and bytes by ID.

Two routes, one addressing rule. **Neither accepts a path**, and there is no
third route that does - architecture §14 requires that no endpoint take an
arbitrary local path, and the way that is guaranteed here is that the only
identifier in either signature is an artifact-version ID.

A traversal string arriving in the path segment is therefore not a special
case: `../../etc/passwd`, encoded or not, is an ID that names no registered
row, and it comes back `404` exactly as `not-a-real-id` does. The containment
check that matters is the one behind the port, over the path a *registration*
holds, and it is reached through the application layer rather than from here.

This router calls no containment code, imports no infrastructure, and never
sees a `Path`. What the application hands it is a stream descriptor and a
filename, and the only thing left to decide is transport.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..dependencies import Services
from ..responses import artifact_response
from ..schemas.artifacts import ArtifactVersionDetailResponse

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


@router.get(
    "/{artifact_version_id}",
    response_model=ArtifactVersionDetailResponse,
    summary="Read one registered artifact's metadata and download eligibility",
)
def artifact_detail(artifact_version_id: str, services: Services) -> ArtifactVersionDetailResponse:
    """`200` with the registration and whether its payload verifies (§20).

    `downloadable` is answered by running the same verification the download
    runs, so the two cannot disagree.
    """
    result = services.queries.artifact_version(artifact_version_id)
    return ArtifactVersionDetailResponse.model_validate(result.model_dump(mode="json"))


@router.get(
    "/{artifact_version_id}/download",
    summary="Download one registered artifact by ID",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "The registered payload, under a safe delivery filename.",
            "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
            },
        }
    },
)
def download_artifact(artifact_version_id: str, services: Services) -> StreamingResponse:
    """`200` and the bytes; `412` when the stored payload does not verify.

    A `404` means no such registration. A `412` means the registration exists
    and its payload failed containment, presence, or its hash - three separate
    codes, because "somebody moved it" and "somebody changed it" are different
    findings and a client should not have to guess which it hit.

    `Content-Length` is set from the size the store measured after verifying
    the hash, so a client can show progress against a number that was true of
    the exact bytes being sent.
    """
    delivery = services.rendering.download_artifact(artifact_version_id)
    return artifact_response(delivery)
