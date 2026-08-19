"""The deterministic pipeline: ingest through ready, plus operation inspection."""

from __future__ import annotations

import json

from ..application.commands import AnalyzeCommand, DraftCommand, IngestCommand, RenderCommand
from ..application.errors import WorkflowError
from ..util import new_id
from .context import CommandContext, _command
from .fast import (
    _job_text,
    _latest_job_analysis_id,
    _latest_job_snapshot_id,
    _latest_selection_plan_id,
)
from .output import _print


@_command("ingest")
def _ingest(context: CommandContext) -> int:
    args = context.args
    ingested = context.built_services.applications.ingest(
        IngestCommand(
            company=args.company,
            target_role=args.role,
            job_text=_job_text(args),
            source_url=args.url,
        )
    )
    _print(
        {
            "application_id": ingested.application_id,
            "job_snapshot_id": ingested.job_snapshot_id,
        }
    )
    return 0


@_command("analyze")
def _analyze(context: CommandContext) -> int:
    args = context.args
    services = context.built_services
    command = AnalyzeCommand(
        application_id=args.application_id,
        job_snapshot_id=(
            args.job_snapshot
            or _latest_job_snapshot_id(context.repository, args.application_id)
        ),
        track_override=args.track,
        profile_override=args.profile,
        emphasis_override=args.emphasis,
        language_override=args.language,
        accept_low_fit=args.accept_low_fit,
        provider=args.provider,
        model=args.model,
    )
    operation = services.operations.submit_analysis(
        command,
        idempotency_key=args.idempotency_key or new_id(),
        analysis_service=services.analysis,
    )
    completed = services.foreground_operations.execute(operation.id)
    if completed.status.value != "succeeded":
        detail = completed.safe_failure_detail or "analysis Operation did not complete"
        code = completed.failure_code.value if completed.failure_code is not None else "UNKNOWN"
        raise WorkflowError(f"{code}: {detail}")
    output_ids = {output.output_type: output.output_id for output in completed.outputs}
    analysed = context.repository.get_analysis(output_ids["job_analysis"])
    _print(
        {
            "operation_id": completed.id,
            "analysis_id": output_ids["job_analysis"],
            "selection_plan_id": output_ids["selection_plan"],
            "analysis": analysed["analysis"].model_dump(mode="json"),
        }
    )
    return 0


@_command("draft")
def _draft(context: CommandContext) -> int:
    args = context.args
    services = context.built_services
    command = DraftCommand(
        application_id=args.application_id,
        job_analysis_id=(
            args.job_analysis
            or _latest_job_analysis_id(context.repository, args.application_id)
        ),
        selection_plan_id=(
            args.selection_plan
            or _latest_selection_plan_id(context.repository, args.application_id)
        ),
    )
    operation = services.operations.submit_draft(
        command,
        idempotency_key=args.idempotency_key or new_id(),
        draft_service=services.drafts,
    )
    completed = services.foreground_operations.execute(operation.id)
    if completed.status.value != "succeeded":
        detail = completed.safe_failure_detail or "draft Operation did not complete"
        code = completed.failure_code.value if completed.failure_code is not None else "UNKNOWN"
        raise WorkflowError(f"{code}: {detail}")
    output_ids = {output.output_type: output.output_id for output in completed.outputs}
    validation = context.repository.latest_validation_for_working_draft(
        output_ids["working_draft"]
    )
    if validation is None:
        raise WorkflowError("draft Operation completed without a ValidationRun")
    paths = services.artifacts.working_paths(args.application_id)
    _print(
        {
            "markdown": str(paths.markdown),
            "claim_manifest": str(paths.manifest),
            "operation_id": completed.id,
            "validation": validation["report"].model_dump(mode="json"),
            "review_required": True,
        }
    )
    return 0


@_command("validate")
def _validate(context: CommandContext) -> int:
    report = context.built_services.drafts.validate_working(context.args.application_id)
    _print(report.model_dump(mode="json"))
    return 0 if report.passed else 1


@_command("approve")
def _approve(context: CommandContext) -> int:
    services = context.built_services
    approved = services.operations.approve_idempotent(
        context.args.application_id,
        idempotency_key=context.args.idempotency_key or new_id(),
        draft_service=services.drafts,
    )
    _print(
        {
            "version": approved.version,
            "directory": str(
                services.artifacts.resolve(
                    context.repository.approved_revision(
                        approved.revision_id
                    ).resume_markdown_reference
                ).parent
            ),
            "revision_id": approved.revision_id,
            "decision_record_id": approved.decision_record_id,
        }
    )
    return 0


@_command("render")
def _render(context: CommandContext) -> int:
    services = context.built_services
    application_id = context.args.application_id
    revision_id = context.repository.latest_approved_revision(application_id).id
    operation = services.operations.submit_render(
        RenderCommand(
            application_id=application_id,
            approved_revision_id=revision_id,
        ),
        idempotency_key=context.args.idempotency_key or new_id(),
        rendering_service=services.rendering,
    )
    completed = services.foreground_operations.execute(operation.id)
    output_ids = {output.output_type: output.output_id for output in completed.outputs}
    if "resume_pdf" not in output_ids:
        detail = completed.safe_failure_detail or "render Operation produced no PDF"
        code = completed.failure_code.value if completed.failure_code is not None else "UNKNOWN"
        raise WorkflowError(f"{code}: {detail}")
    pdf_record = context.repository.artifact_version(output_ids["resume_pdf"])
    pdf_metadata = json.loads(pdf_record.get("metadata_json") or "{}")
    report = context.repository.validation_for_artifact(
        application_id, "post-render", output_ids["resume_pdf"]
    )
    _print(
        {
            "operation_id": completed.id,
            "pdf": str(services.artifacts.resolve(pdf_record["path"])),
            "filename": pdf_metadata.get("recruiter_filename"),
            "ready_validation": report.model_dump(mode="json"),
        }
    )
    return 0 if completed.status.value == "succeeded" and report.passed else 1


@_command("ready")
def _ready(context: CommandContext) -> int:
    report = context.built_services.rendering.ready_report(context.args.application_id)
    _print(report.model_dump(mode="json"))
    return 0 if report.passed else 1


@_command("operation")
def _operation(context: CommandContext) -> int:
    args = context.args
    services = context.built_services
    if args.operation_command == "show":
        result = services.operations.get(args.operation_id)
    elif args.operation_command == "cancel":
        result = services.operations.cancel(args.operation_id)
    else:
        queued = services.operations.retry(
            args.operation_id,
            idempotency_key=args.idempotency_key,
        )
        result = services.foreground_operations.execute(queued.id)
    _print(result)
    if args.operation_command == "retry" and result.status.value != "succeeded":
        return 1
    return 0
