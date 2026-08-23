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


class HealthResponse(HttpSchema):
    """What `cv web` probes to tell its own instance from a foreign process.

    `installation_id` and `workspace_id` together answer "is the process on this
    port mine, and is it serving the Workspace I am about to open". The version
    surfaces are the §17 provenance set, reported so a client can refuse to talk
    to an instance it does not understand.
    """

    status: str
    installation_id: str
    workspace_id: str
    product_version: str
    api_version: str
    schema_version: str
    knowledge: KnowledgeVersions
