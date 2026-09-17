"""Durable Operation submission, lifecycle, replacement, and execution handlers."""

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
from .lifecycle import OperationLifecycleService
from .replacement import OperationReplacementService
from .service import OperationSubmissionService

__all__ = [
    "FAILURE_CODE_BY_ERROR",
    "AITaskHandler",
    "AnalysisOperationHandler",
    "DraftOperationHandler",
    "OperationLifecycleService",
    "OperationReplacementService",
    "OperationSubmissionService",
    "RegenerationOperationHandler",
    "RenderOperationHandler",
    "SelectionPlanOperationHandler",
    "analysis_knowledge_context_hash",
    "failure_code_for",
    "safe_failure_detail_for",
]
