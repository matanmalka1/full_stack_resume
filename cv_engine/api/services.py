"""What the API is given, and nothing more.

`runtime.Services` holds repositories, stores, a renderer, a provider, and the
Operation worker. A router needs none of those, and being able to reach one is
how business logic ends up in a router. `ApiServices` is the narrow container the
composition root fills in: application services, plus the two plain values the
API itself needs to answer for.

Declared here rather than in `runtime/` so the dependency points inward -
`runtime` imports `api`, never the other way around.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..application.services.analysis import AnalysisService
from ..application.services.applications import ApplicationService
from ..application.services.drafts import DraftService
from ..application.services.knowledge import KnowledgeService
from ..application.services.operations import OperationService
from ..application.services.projections import ApplicationQueryService
from ..application.services.rendering import RenderingService
from ..application.services.tracking import TrackingService
from ..application.settings import SettingsService


@dataclass(frozen=True)
class InstanceIdentity:
    """Version identity exposed by the local process."""

    product_version: str
    api_version: str
    schema_version: str


@dataclass(frozen=True)
class ApiLimits:
    """Transport limits, resolved by the config layer rather than hardcoded here.

    `dev_origin` is unset in production: the built UI is served same-origin, so
    there is no second origin to allow. When set it is exactly one origin - the
    development Vite server - never a wildcard and never a list.
    """

    max_body_bytes: int
    dev_origin: str | None = None


@dataclass(frozen=True)
class ApiServices:
    applications: ApplicationService
    queries: ApplicationQueryService
    analysis: AnalysisService
    drafts: DraftService
    rendering: RenderingService
    tracking: TrackingService
    knowledge: KnowledgeService
    operations: OperationService
    settings: SettingsService
    identity: InstanceIdentity
    limits: ApiLimits
