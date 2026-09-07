"""The base boundary DTO type. Dependency-free so every domain module can use
it without risking a cycle with `shared.py`, which itself depends on
`knowledge.py` for the combined reconciliation report.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class BoundaryDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


#: Who a new record may name as its originating client. There is no default: a
#: command that records who acted must be told, because a wrong default is
#: indistinguishable from a correct one once it is in the audit trail.
WriteClient = Literal["web", "worker"]

DuplicateMatchReason = Literal["source_url", "normalized_text", "company_title"]
