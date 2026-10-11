"""Derived guard for ownership-bearing persistence Protocols (architecture §18.3)."""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path

PORTS_ROOT = Path(__file__).resolve().parents[2] / "cv_engine" / "application" / "ports"
CHILD_IDS = frozenset(
    {"analysis_id", "event_id", "operation_id", "submission_id", "document_id", "output_id"}
)

# Each entry is deliberately internal: the service already resolved the Application,
# it is worker-only and derives the owner from the Operation, or it is the retired
# single-user mutation journal. A stale exception fails because the discovered set
# must equal this set exactly.
SCOPED_BY_CALLER = frozenset(
    {
        ("ai_calls", "AICallLog", "append"),
        ("analysis_plans", "AnalysisStore", "refuse_matching_context_operation"),
        ("application_intake", "InitialRecruitmentEventWriter", "insert_initial_saved_event"),
        ("application_projections", "ApplicationProjectionReader", "has_submission"),
        ("application_projections", "ApplicationProjectionReader", "analyses"),
        ("application_projections", "ApplicationProjectionReader", "analysis"),
        ("application_projections", "ApplicationProjectionReader", "recruitment_events"),
        ("application_projections", "ApplicationProjectionReader", "submissions"),
        ("application_projections", "ApplicationProjectionReader", "audit_records"),
        ("application_projections", "ApplicationProjectionReader", "active_operation"),
        ("application_projections", "ApplicationProjectionReader", "latest_operation"),
        (
            "application_projections",
            "ApplicationProjectionReader",
            "has_active_matching_context_operation",
        ),
        ("documents", "DocumentStore", "document"),
        ("documents", "DocumentStore", "lock_document"),
        ("documents", "DocumentStore", "create_document"),
        ("documents", "DocumentStore", "update_body"),
        ("documents", "DocumentStore", "repin"),
        ("documents", "DocumentStore", "stamp_check"),
        ("documents", "DocumentStore", "stamp_approval"),
        ("documents", "DocumentStore", "activate_render"),
        ("documents", "DocumentStore", "record_render_error"),
        ("documents", "DocumentFileStore", "render_targets"),
        ("documents", "DocumentFileStore", "copy_for_submission"),
        ("documents", "DocumentSubmissionStore", "submissions"),
        ("knowledge_lifecycle", "KnowledgeLifecycleStore", "get_analysis"),
        ("operation_execution", "OperationExecutionStore", "operation"),
        ("operation_execution", "OperationExecutionStore", "claim_operation"),
        ("operation_execution", "OperationExecutionStore", "lock_application"),
        ("operation_execution", "OperationExecutionStore", "cancellation_requested"),
        ("operation_execution", "OperationExecutionStore", "execution_still_owned"),
        ("operation_execution", "OperationExecutionStore", "record_operation_output"),
        ("operation_execution", "OperationExecutionStore", "complete_operation"),
        ("operation_execution", "OperationExecutionStore", "fail_operation"),
        ("recruitment", "RecruitmentStore", "event"),
        ("recruitment", "RecruitmentStore", "insert_event"),
        ("recruitment", "RecruitmentStore", "insert_next_action"),
    }
)


def test_persistence_protocols_never_resolve_owned_ids_without_scope() -> None:
    discovered: set[tuple[str, str, str]] = set()
    for path in sorted(PORTS_ROOT.glob("*.py")):
        if path.name.startswith("_"):
            continue
        module = importlib.import_module(f"cv_engine.application.ports.{path.stem}")
        for class_name, contract in vars(module).items():
            if not inspect.isclass(contract) or contract.__module__ != module.__name__:
                continue
            for method_name, method in vars(contract).items():
                if method_name.startswith("_") or not callable(method):
                    continue
                parameters = set(inspect.signature(method).parameters) - {"self", "tx"}
                unscoped_root = "application_id" in parameters and "user_id" not in parameters
                unscoped_child = bool(parameters & CHILD_IDS) and not (
                    parameters & {"application_id", "user_id"}
                )
                if unscoped_root or unscoped_child:
                    discovered.add((path.stem, class_name, method_name))

    assert discovered == SCOPED_BY_CALLER
