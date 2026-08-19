"""Legacy-signature resolvers and the fast no-pause flow that chains them.

`_latest_*` fill in the source ID a v1 CLI signature omitted; `_fast` is the
explicit no-pause flow itself, an approval instruction rather than a bypass,
recorded as such and passing through every validation and blocker unchanged.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ..application.commands import AnalyzeCommand, DraftCommand, IngestCommand, RenderCommand
from ..application.errors import WorkflowError
from ..runtime.composition import Services
from ..util import new_id
from .context import CommandContext, _command
from .output import _print


def _job_text(args: argparse.Namespace) -> str:
    if getattr(args, "job_file", None):
        return Path(args.job_file).read_text(encoding="utf-8")
    if getattr(args, "job_text", None):
        return args.job_text
    raise ValueError("one of --job-file or --job-text is required")


def _latest_job_snapshot_id(repository: Any, application_id: str) -> str:
    """The snapshot a legacy CLI signature meant when it named none.

    v2 commands take explicit source IDs. The v1 CLI signatures do not carry
    one, so the resolution happens here, at the CLI boundary, where `latest`
    is a query convenience rather than part of what a command means.
    """
    return repository.latest_snapshot(application_id)["id"]


def _latest_job_analysis_id(repository: Any, application_id: str) -> str:
    """The analysis a legacy CLI signature meant when it named none."""
    return repository.latest_analysis(application_id)[0]


def _latest_selection_plan_id(repository: Any, application_id: str) -> str:
    """The immutable plan a legacy CLI signature meant when it named none."""
    return repository.latest_selection_plan(application_id).id


def _fast(
    services: Services,
    company: str,
    role: str,
    job_text: str,
    *,
    url: str | None = None,
    track: str | None = None,
    profile: str | None = None,
    emphasis: str | None = None,
    language: str | None = None,
    accept_low_fit: bool = False,
) -> dict[str, Any]:
    """The explicit no-pause flow: an approval instruction, not a bypass.

    Invoking it is itself the user's approval decision, recorded as such.
    It chains the same use-cases in the same order and every validation and
    blocker still applies; nothing here can approve unvalidated content.
    """
    ingested = services.applications.ingest(
        IngestCommand(
            company=company,
            target_role=role,
            job_text=job_text,
            source_url=url,
        )
    )
    analysis_operation = services.operations.submit_analysis(
        AnalyzeCommand(
            application_id=ingested.application_id,
            job_snapshot_id=ingested.job_snapshot_id,
            track_override=track,
            profile_override=profile,
            emphasis_override=emphasis,
            language_override=language,
            accept_low_fit=accept_low_fit,
        ),
        idempotency_key=new_id(),
        analysis_service=services.analysis,
    )
    analysed = services.foreground_operations.execute(analysis_operation.id)
    if analysed.status.value != "succeeded":
        detail = analysed.safe_failure_detail or "analysis Operation did not complete"
        code = analysed.failure_code.value if analysed.failure_code is not None else "UNKNOWN"
        raise WorkflowError(f"{code}: {detail}")
    analysis_outputs = {output.output_type: output.output_id for output in analysed.outputs}

    draft_operation = services.operations.submit_draft(
        DraftCommand(
            application_id=ingested.application_id,
            job_analysis_id=analysis_outputs["job_analysis"],
            selection_plan_id=analysis_outputs["selection_plan"],
        ),
        idempotency_key=new_id(),
        draft_service=services.drafts,
    )
    drafted = services.foreground_operations.execute(draft_operation.id)
    if drafted.status.value != "succeeded":
        detail = drafted.safe_failure_detail or "draft Operation did not complete"
        code = drafted.failure_code.value if drafted.failure_code is not None else "UNKNOWN"
        raise WorkflowError(f"{code}: {detail}")
    draft_outputs = {output.output_type: output.output_id for output in drafted.outputs}
    draft_validation = services.repository.latest_validation_for_working_draft(
        draft_outputs["working_draft"]
    )
    if draft_validation is None:
        raise WorkflowError("draft Operation completed without a ValidationRun")
    if not draft_validation["report"].passed:
        raise WorkflowError("fast mode blocked by pre-render validation")
    approved = services.operations.approve_idempotent(
        ingested.application_id,
        idempotency_key=new_id(),
        draft_service=services.drafts,
    )
    render_operation = services.operations.submit_render(
        RenderCommand(
            application_id=ingested.application_id,
            approved_revision_id=approved.revision_id,
        ),
        idempotency_key=new_id(),
        rendering_service=services.rendering,
    )
    rendered = services.foreground_operations.execute(render_operation.id)
    render_outputs = {output.output_type: output.output_id for output in rendered.outputs}
    if "resume_pdf" not in render_outputs:
        detail = rendered.safe_failure_detail or "render Operation produced no PDF"
        code = rendered.failure_code.value if rendered.failure_code is not None else "UNKNOWN"
        raise WorkflowError(f"{code}: {detail}")
    pdf_record = services.repository.artifact_version(render_outputs["resume_pdf"])
    render_validation = services.repository.validation_for_artifact(
        ingested.application_id, "post-render", render_outputs["resume_pdf"]
    )
    if rendered.status.value != "succeeded" or not render_validation.passed:
        raise WorkflowError("fast mode blocked by post-render validation")
    qualification = services.rendering.ready_qualification(
        ingested.application_id,
        approved.revision_id,
        render_outputs["resume_pdf"],
    )
    pdf_metadata = json.loads(pdf_record.get("metadata_json") or "{}")
    return {
        "application_id": ingested.application_id,
        "approval": {
            "version": approved.version,
            "directory": services.artifacts.resolve(
                services.repository.approved_revision(
                    approved.revision_id
                ).resume_markdown_reference
            ).parent,
            "revision_id": approved.revision_id,
            "decision_record_id": approved.decision_record_id,
        },
        "pdf": str(services.artifacts.resolve(pdf_record["path"])),
        "filename": pdf_metadata.get("recruiter_filename"),
        "ready": qualification.ready_qualified,
    }


@_command("fast")
def _fast_command(context: CommandContext) -> int:
    args = context.args
    _print(
        _fast(
            context.built_services,
            args.company,
            args.role,
            _job_text(args),
            url=args.url,
            track=args.track,
            profile=args.profile,
            emphasis=args.emphasis,
            language=args.language,
            accept_low_fit=args.accept_low_fit,
        )
    )
    return 0
