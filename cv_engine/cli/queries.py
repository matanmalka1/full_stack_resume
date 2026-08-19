"""Commands that report on or transition an application's tracked state."""

from __future__ import annotations

import sys

from ..application.commands import (
    ExternalSubmissionCommand,
    NextActionCommand,
    RecruitmentCorrectionCommand,
    RecruitmentStatusCommand,
    SubmissionCommand,
)
from .context import CommandContext, _command
from .output import _print


@_command("list")
def _list(context: CommandContext) -> int:
    _print(context.built_services.queries.list_applications())
    return 0


@_command("show")
def _show(context: CommandContext) -> int:
    _print(context.built_services.queries.application_detail(context.args.application_id))
    return 0


@_command("versions")
def _versions(context: CommandContext) -> int:
    _print(context.built_services.queries.artifact_versions(context.args.application_id))
    return 0


@_command("decision")
def _decision(context: CommandContext) -> int:
    _print(context.built_services.queries.latest_decision(context.args.application_id))
    return 0


@_command("status")
def _status(context: CommandContext) -> int:
    args = context.args
    _print(
        context.built_services.tracking.transition_status(
            RecruitmentStatusCommand(
                application_id=args.application_id,
                target_status=args.status,
                reason=args.reason,
            )
        )
    )
    return 0


@_command("correct-status")
def _correct_status(context: CommandContext) -> int:
    args = context.args
    _print(
        context.built_services.tracking.correct_recruitment_status(
            RecruitmentCorrectionCommand(
                application_id=args.application_id,
                target_status=args.status,
                corrects_event_id=args.corrects_event,
                reason=args.reason,
                occurred_at=args.occurred_at,
            )
        )
    )
    return 0


@_command("submit")
def _submit(context: CommandContext) -> int:
    args = context.args
    _print(
        context.built_services.tracking.submit_application(
            SubmissionCommand(
                application_id=args.application_id,
                approved_revision_id=args.revision,
                pdf_artifact_version_id=args.pdf_artifact,
                submitted_at=args.submitted_at,
                metadata={"note": args.note} if args.note else {},
            )
        )
    )
    return 0


@_command("external-submit")
def _external_submit(context: CommandContext) -> int:
    args = context.args
    _print(
        context.built_services.tracking.record_external_submission(
            ExternalSubmissionCommand(
                application_id=args.application_id,
                artifact_version_id=args.artifact,
                submitted_at=args.submitted_at,
                metadata={"note": args.note} if args.note else {},
            )
        )
    )
    return 0


@_command("decision-markdown")
def _decision_markdown(context: CommandContext) -> int:
    args = context.args
    exported = context.built_services.drafts.export_decision_markdown(
        args.application_id, args.revision
    )
    if args.output is None:
        sys.stdout.write(exported.content)
    else:
        args.output.write_text(exported.content, encoding="utf-8")
        _print(
            {
                "application_id": exported.application_id,
                "approved_revision_id": exported.approved_revision_id,
                "output": str(args.output),
                "content_hash": exported.content_hash,
            }
        )
    return 0


@_command("action")
def _action(context: CommandContext) -> int:
    args = context.args
    _print(
        context.built_services.tracking.set_next_action(
            NextActionCommand(
                application_id=args.application_id,
                next_action=args.next_action,
                next_action_date=args.date,
            )
        )
    )
    return 0
