"""Commands that edit or sync working-draft claims against facts."""

from __future__ import annotations

from typing import Any

from ..runtime.composition import Services
from .context import CommandContext, _command
from .output import _print


def _print_claim_edit(services: Services, application_id: str, edited: Any) -> int:
    """The one shape every claim edit reports: the draft path and its validation."""
    _print(
        {
            "markdown": str(services.artifacts.working_paths(application_id).markdown),
            "validation": edited.validation.model_dump(mode="json"),
        }
    )
    return 0 if edited.validation.passed else 1


@_command("edit-claim")
def _edit_claim(context: CommandContext) -> int:
    args = context.args
    services = context.built_services
    edited = services.drafts.edit_claim(
        args.application_id,
        args.claim_id,
        args.fact_id,
        text=args.text,
        template_id=args.template,
        template_version=args.template_version,
    )
    return _print_claim_edit(services, args.application_id, edited)


@_command("sync-draft")
def _sync_draft(context: CommandContext) -> int:
    services = context.built_services
    edited = services.drafts.sync_working_claims(context.args.application_id)
    return _print_claim_edit(services, context.args.application_id, edited)
