from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class HttpSchema(BaseModel):
    """Base for every HTTP schema: unknown fields are an error, not a shrug."""

    model_config = ConfigDict(extra="forbid")


class KnowledgeVersions(HttpSchema):
    facts: str
    facts_lifecycle: str
    profiles: str
    emphasis_policies: str
    presentations: str
    candidate_context: str
    requirement_concepts: str


class HealthResponse(HttpSchema):
    """Health and version surfaces for the local process."""

    status: str
    product_version: str
    api_version: str
    schema_version: str
    knowledge: KnowledgeVersions
