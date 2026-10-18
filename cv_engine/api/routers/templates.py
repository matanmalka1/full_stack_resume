"""The render templates a CV can choose, shown before any CV of the user's exists.

The catalog itself is part of the settings read; this serves what each template
looks like, over a fictional sample CV that belongs to no user.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from ..dependencies import Services
from ..schemas.documents import PreviewTemplateParameter

router = APIRouter(prefix="/templates", tags=["templates"])

#: The same framing-only policy as the document preview: inline style and nothing else.
_SAMPLE_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; form-action 'none'; base-uri 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "private, max-age=300",
}


@router.get(
    "/{template}/sample",
    summary="Render the sample CV in one template, for an isolated preview",
    response_class=HTMLResponse,
    responses={
        200: {
            "description": "A fictional CV through the same composition the render uses.",
            "content": {"text/html": {"schema": {"type": "string"}}},
        }
    },
)
def sample_template(
    template: PreviewTemplateParameter, services: Services, language: Literal["en", "he"] = "en"
) -> HTMLResponse:
    """`200` and the sample CV; `track` is the track's own template."""
    return HTMLResponse(
        content=services.rendering.sample_template(template, language),
        headers=_SAMPLE_HEADERS,
    )
