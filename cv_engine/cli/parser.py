"""The argparse tree: every cv command, subcommand, and flag."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..domain.facts import FACT_SOURCE_NAMES
from ..domain.models import ApplicationStatus, FactStatus


def _add_job_input(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--company", required=True)
    parser.add_argument("--role", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--job-file")
    group.add_argument("--job-text")
    parser.add_argument("--url")
    parser.add_argument(
        "--acknowledge-duplicates",
        action="store_true",
        help="create even when duplicate warnings match an existing application",
    )


def _add_overrides(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--track", choices=["development", "sales", "tech-sales"])
    parser.add_argument("--profile")
    parser.add_argument("--emphasis")
    parser.add_argument("--language", choices=["en", "he"])
    parser.add_argument("--accept-low-fit", action="store_true")


def _add_fact_content(parser: argparse.ArgumentParser, *, from_claim: bool = False) -> None:
    """Arguments that describe a fact's content on creation.

    `--canonical` is the spec's explicit "add this to the source of truth"
    confirmation and the only way to skip `pending`; everything else must walk
    the lifecycle.
    """
    parser.add_argument("--source", required=True, choices=list(FACT_SOURCE_NAMES))
    parser.add_argument("--fact-id", required=True)
    parser.add_argument("--meaning", required=True, help="language-neutral meaning")
    parser.add_argument("--en", required=not from_claim, help="English rendering")
    parser.add_argument("--he", help="Hebrew rendering")
    parser.add_argument("--tag", action="append", default=[], required=True)
    if not from_claim:
        parser.add_argument(
            "--style",
            required=True,
            choices=["paragraph", "heading", "date", "bullet", "item", "contact"],
        )
    parser.add_argument("--provenance", required=not from_claim)
    parser.add_argument("--dates", help="effective or event dates")
    parser.add_argument("--replaces", help="fact_id this fact supersedes")
    parser.add_argument(
        "--canonical",
        action="store_true",
        help="explicit confirmation in this request; writes the fact as canonical",
    )
    parser.add_argument("--reason", default="")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cv", description="Multi-track fact-safe CV engine")
    parser.add_argument("--workspace", type=Path, help="Workspace root; must carry a v2 marker")
    parser.add_argument(
        "--repo",
        type=Path,
        help="deprecated alias for --workspace",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    web = sub.add_parser("web", help="start the local Web UI, API, and Operation worker")
    web.add_argument("--no-open", action="store_true", help="do not open the default browser")
    web.add_argument("--port", type=int, help="preferred loopback port; defaults to 8765")

    workspace = sub.add_parser("workspace", help="create and inspect the local Workspace")
    workspace_sub = workspace.add_subparsers(dest="workspace_command", required=True)
    workspace_init = workspace_sub.add_parser(
        "init", help="create an isolated Workspace and its marker"
    )
    workspace_init.add_argument(
        "--purpose", choices=["development", "test", "live"], default="development"
    )
    workspace_init.add_argument("--data-class", choices=["copy", "test", "live"], default="copy")
    workspace_init.add_argument(
        "--knowledge-from",
        type=Path,
        help="copy base/profiles/rendering/config/ai from this directory into the new Workspace",
    )
    workspace_sub.add_parser(
        "status", help="show Workspace identity, roots, and resolved configuration"
    )
    ingest = sub.add_parser("ingest", help="create an application and immutable job snapshot")
    _add_job_input(ingest)

    analyze = sub.add_parser("analyze", help="classify Track/Profile/Emphasis and fit")
    analyze.add_argument("application_id")
    _add_overrides(analyze)
    analyze.add_argument("--provider", choices=["deterministic", "openai"], default="deterministic")
    analyze.add_argument("--model", default="gpt-5.6")
    analyze.add_argument("--idempotency-key")
    # v2 commands take an explicit source ID. The legacy signature omits it,
    # so the CLI-boundary resolver fills it in when the flag is absent.
    analyze.add_argument("--job-snapshot", dest="job_snapshot", default=None)

    draft = sub.add_parser("draft", help="create or update the active working draft")
    draft.add_argument("application_id")
    draft.add_argument("--job-analysis", dest="job_analysis", default=None)
    draft.add_argument("--selection-plan", dest="selection_plan", default=None)
    draft.add_argument("--idempotency-key")

    for name, help_text in [
        ("validate", "run pre-render validation"),
        ("approve", "approve and version the working draft"),
        ("render", "render the latest approved version and run ready checks"),
        ("ready", "inspect the complete ready validation result"),
        ("show", "inspect one application"),
        ("versions", "inspect artifact versions"),
        ("decision", "inspect the latest decision record"),
    ]:
        command = sub.add_parser(name, help=help_text)
        command.add_argument("application_id")
        if name in {"approve", "render"}:
            command.add_argument("--idempotency-key")

    fast = sub.add_parser("fast", help="explicit no-pause flow; validation remains mandatory")
    _add_job_input(fast)
    _add_overrides(fast)

    operation = sub.add_parser("operation", help="inspect, cancel, or retry durable work")
    operation_sub = operation.add_subparsers(dest="operation_command", required=True)
    operation_show = operation_sub.add_parser("show")
    operation_show.add_argument("operation_id")
    operation_cancel = operation_sub.add_parser("cancel")
    operation_cancel.add_argument("operation_id")
    operation_retry = operation_sub.add_parser("retry")
    operation_retry.add_argument("operation_id")
    operation_retry.add_argument("--idempotency-key", required=True)

    sub.add_parser("list", help="list applications")
    status = sub.add_parser("status", help="transition application status with immutable history")
    status.add_argument("application_id")
    status.add_argument(
        "status",
        choices=[item.value for item in ApplicationStatus if item is not ApplicationStatus.APPLIED],
        help="applied is submission-owned; use submit or external-submit",
    )
    status.add_argument("--reason", default="manual CLI transition")
    correction = sub.add_parser(
        "correct-status", help="append a reasoned correction to recruitment history"
    )
    correction.add_argument("application_id")
    correction.add_argument("status", choices=[item.value for item in ApplicationStatus])
    correction.add_argument("--corrects-event", required=True)
    correction.add_argument("--reason", required=True)
    correction.add_argument("--occurred-at")
    submit = sub.add_parser(
        "submit", help="record an internal submission for one exact qualified revision and PDF"
    )
    submit.add_argument("application_id")
    submit.add_argument("--revision", required=True)
    submit.add_argument("--pdf-artifact", required=True)
    submit.add_argument("--submitted-at", required=True)
    submit.add_argument("--note")
    external_submit = sub.add_parser(
        "external-submit", help="record a submission without inventing a revision or artifact"
    )
    external_submit.add_argument("application_id")
    external_submit.add_argument("--submitted-at", required=True)
    external_submit.add_argument("--artifact")
    external_submit.add_argument("--note")
    decision_markdown = sub.add_parser(
        "decision-markdown", help="export human-readable provenance for one approved revision"
    )
    decision_markdown.add_argument("application_id")
    decision_markdown.add_argument("--revision", required=True)
    decision_markdown.add_argument("--output", type=Path)
    action = sub.add_parser("action", help="set or clear the next action")
    action.add_argument("application_id")
    action.add_argument("--next-action")
    action.add_argument("--date")
    edit = sub.add_parser(
        "edit-claim",
        help="classify and save a canonical, derived, composite, or pending claim edit",
    )
    edit.add_argument("application_id")
    edit.add_argument("claim_id")
    edit_mode = edit.add_mutually_exclusive_group(required=True)
    edit_mode.add_argument("--text")
    edit_mode.add_argument("--template", choices=["canonical-renderings"])
    edit.add_argument("--template-version", default="1.0.0")
    edit.add_argument("--fact-id", action="append", required=True)
    sync = sub.add_parser(
        "sync-draft", help="extract marked manual Markdown edits and classify their claims"
    )
    sync.add_argument("application_id")
    link = sub.add_parser("link-claim", help="compatibility alias for a text-based claim edit")
    link.add_argument("application_id")
    link.add_argument("claim_id")
    link.add_argument("--text", required=True)
    link.add_argument("--fact-id", action="append", required=True)
    export = sub.add_parser("export", help="export application data to CSV")
    export.add_argument("output", type=Path)
    sub.add_parser(
        "reconcile", help="reconcile database references, artifact hashes, and the fact lifecycle"
    )

    fact = sub.add_parser(
        "fact", help="manage the pending -> confirmed -> canonical fact lifecycle"
    )
    fact_sub = fact.add_subparsers(dest="fact_command", required=True)
    fact_list = fact_sub.add_parser("list", help="list stored facts and their lifecycle status")
    fact_list.add_argument("--status", choices=[item.value for item in FactStatus])
    fact_show = fact_sub.add_parser("show", help="inspect one fact and its lifecycle events")
    fact_show.add_argument("fact_id")
    fact_add = fact_sub.add_parser(
        "add", help="create a new fact; pending unless explicitly confirmed"
    )
    _add_fact_content(fact_add)
    fact_capture = fact_sub.add_parser(
        "capture",
        help="create a fact from an unsupported manual claim in the working draft",
    )
    fact_capture.add_argument("application_id")
    fact_capture.add_argument("claim_id")
    _add_fact_content(fact_capture, from_claim=True)
    fact_confirm = fact_sub.add_parser("confirm", help="promote pending -> confirmed")
    fact_confirm.add_argument("fact_id")
    fact_confirm.add_argument(
        "--confirm", action="store_true", help="required explicit confirmation"
    )
    fact_confirm.add_argument("--reason", default="")
    fact_promote = fact_sub.add_parser("promote", help="promote confirmed -> canonical")
    fact_promote.add_argument("fact_id")
    fact_promote.add_argument(
        "--confirm", action="store_true", help="required explicit confirmation"
    )
    fact_promote.add_argument("--reason", default="")
    fact_attach = fact_sub.add_parser(
        "attach",
        help="offer a canonical fact to a Profile section so it can be selected",
    )
    fact_attach.add_argument("fact_id")
    fact_attach.add_argument("--profile", required=True)
    fact_attach.add_argument("--section", required=True)
    fact_attach.add_argument("--pin", action="store_true")
    fact_history = fact_sub.add_parser("history", help="read the immutable fact lifecycle trail")
    fact_history.add_argument("fact_id", nargs="?")

    return parser
