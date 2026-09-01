"""Durable Operations: the handlers that run one, and the service that records it.

`OperationService` and the six handlers are the whole public surface, and the
composition root imports them from here. The split behind it is by
collaborator: a new Operation type touches `handlers` alone, an idempotency or
submission change touches `service` alone.
"""

from __future__ import annotations

from .common import analysis_knowledge_context_hash
from .failures import FAILURE_CODE_BY_ERROR, failure_code_for, safe_failure_detail_for
from .handlers import (
    AITaskHandler,
    AnalysisOperationHandler,
    DraftOperationHandler,
    RegenerationOperationHandler,
    RenderOperationHandler,
    SelectionPlanOperationHandler,
)
from .service import OperationService

__all__ = [
    "FAILURE_CODE_BY_ERROR",
    "AITaskHandler",
    "AnalysisOperationHandler",
    "DraftOperationHandler",
    "OperationService",
    "RegenerationOperationHandler",
    "RenderOperationHandler",
    "SelectionPlanOperationHandler",
    "analysis_knowledge_context_hash",
    "failure_code_for",
    "safe_failure_detail_for",
]
