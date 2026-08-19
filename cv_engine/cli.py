from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .application.commands import (
    AnalyzeCommand,
    DraftCommand,
    ExternalSubmissionCommand,
    IngestCommand,
    NextActionCommand,
    RecruitmentCorrectionCommand,
    RecruitmentStatusCommand,
    SubmissionCommand,
)
from .application.errors import WorkflowError
from .application.ports import ApplicationRepository, ApplicationStore
from .application.queries import ApplicationListView
from .domain.facts import FACT_SOURCE_NAMES
from .domain.models import ApplicationStatus, FactStatus
from .infrastructure.legacy_source import LegacySourceError, LegacyV1Source
from .infrastructure.migration import (
    MigrationSafetyError,
    retrospective_verify_migration,
    verify_source,
)
from .infrastructure.paths import resolve_within
from .infrastructure.persistence import current_schema_version, initialize
from .runtime.composition import Services, build_services
from .runtime.config import resolve_config
from .runtime.workspace import Workspace, WorkspaceError, create_workspace, load_workspace
from .util import utc_now, verify_payload


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _print(value: Any) -> None:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


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
    analysed = services.analysis.analyze(
        AnalyzeCommand(
            application_id=ingested.application_id,
            job_snapshot_id=ingested.job_snapshot_id,
            track_override=track,
            profile_override=profile,
            emphasis_override=emphasis,
            language_override=language,
            accept_low_fit=accept_low_fit,
        )
    )
    drafted = services.drafts.draft(
        DraftCommand(
            application_id=ingested.application_id,
            job_analysis_id=analysed.analysis_id,
            selection_plan_id=analysed.selection_plan_id,
        )
    )
    if not drafted.validation.passed:
        raise WorkflowError("fast mode blocked by pre-render validation")
    approved = services.drafts.approve(ingested.application_id)
    rendered = services.rendering.render(ingested.application_id)
    if not rendered.validation.passed:
        raise WorkflowError("fast mode blocked by post-render validation")
    qualification = services.rendering.ready_qualification(
        ingested.application_id,
        approved.revision_id,
        rendered.pdf_artifact_version_id,
    )
    pdf_record = services.repository.latest_artifact_version(ingested.application_id, "resume_pdf")
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


def _add_job_input(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--company", required=True)
    parser.add_argument("--role", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--job-file")
    group.add_argument("--job-text")
    parser.add_argument("--url")


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
    parser.add_argument("--db", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)

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
    workspace_inventory = workspace_sub.add_parser(
        "inventory-legacy",
        help="read-only inventory of an unmarked legacy v1 source",
    )
    workspace_inventory.add_argument("--source", type=Path, required=True)

    sub.add_parser("init", help="initialize the v1 SQLite schema")
    ingest = sub.add_parser("ingest", help="create an application and immutable job snapshot")
    _add_job_input(ingest)

    analyze = sub.add_parser("analyze", help="classify Track/Profile/Emphasis and fit")
    analyze.add_argument("application_id")
    _add_overrides(analyze)
    analyze.add_argument("--provider", choices=["deterministic", "openai"], default="deterministic")
    analyze.add_argument("--model", default="gpt-5.6")
    # v2 commands take an explicit source ID. The legacy signature omits it,
    # so the CLI-boundary resolver fills it in when the flag is absent.
    analyze.add_argument("--job-snapshot", dest="job_snapshot", default=None)

    draft = sub.add_parser("draft", help="create or update the active working draft")
    draft.add_argument("application_id")
    draft.add_argument("--job-analysis", dest="job_analysis", default=None)
    draft.add_argument("--selection-plan", dest="selection_plan", default=None)

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

    fast = sub.add_parser("fast", help="explicit no-pause flow; validation remains mandatory")
    _add_job_input(fast)
    _add_overrides(fast)

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
        "reconcile", help="reconcile SQLite references, artifact hashes, and the fact lifecycle"
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

    migrate = sub.add_parser("migrate", help="read-only verification of the completed v1 migration")
    migrate_sub = migrate.add_subparsers(dest="migration_command", required=True)
    migrate_sub.add_parser(
        "verify-source", help="re-derive the frozen v1 source from Git and its database backup"
    )
    migrate_sub.add_parser(
        "verify-live", help="read-only semantic verification of the completed migration"
    )
    return parser


EXPORT_SCHEMA_VERSION = "2.0"


def export_csv(applications: ApplicationListView | ApplicationStore, output: Path) -> Path:
    """Export applications with an explicit, versioned schema.

    The v1 export had no version marker, so a consumer could not tell which
    columns to expect. No such consumer was found in this repository, so the
    v2 export keeps the same columns and records the schema beside them rather
    than inventing a compatibility mode nothing asked for.
    """
    rows = (
        [item.model_dump(mode="json") for item in applications.items]
        if isinstance(applications, ApplicationListView)
        else applications.list_applications()
    )
    fields = [
        "id",
        "company",
        "target_role",
        "normalized_role",
        "source_url",
        "language",
        "track",
        "profile",
        "emphasis",
        "classification_confidence",
        "fit_level",
        "current_status",
        "last_contact_date",
        "next_action",
        "next_action_date",
        "notes",
        "source",
        "created_at",
        "updated_at",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field) for field in fields} for row in rows)
    output.with_suffix(output.suffix + ".meta.json").write_text(
        json.dumps(
            {
                "export_schema_version": EXPORT_SCHEMA_VERSION,
                "columns": fields,
                "row_count": len(rows),
                "generated_at": utc_now(),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return output


def fact_command(knowledge: Any, args: argparse.Namespace) -> int:
    """Dispatch the fact lifecycle commands.

    Promotion is refused without `--confirm`: the confirmation is what the
    specification requires for a status change, so an unconfirmed request must
    fail rather than be interpreted.
    """
    if args.fact_command == "list":
        result = knowledge.list_facts(args.status)
        _print(
            [
                {**item.fact.model_dump(mode="json"), "recorded_status": item.recorded_status}
                for item in result.items
            ]
        )
    elif args.fact_command == "show":
        result = knowledge.show_fact(args.fact_id)
        _print(
            {
                **result.fact.model_dump(mode="json"),
                "events": [event.model_dump(mode="json") for event in result.events],
            }
        )
    elif args.fact_command == "history":
        _print(
            [event.model_dump(mode="json") for event in knowledge.fact_history(args.fact_id).events]
        )
    elif args.fact_command == "add":
        renderings = {"en": args.en}
        if args.he:
            renderings["he"] = args.he
        _print(
            knowledge.add_fact(
                args.source,
                {
                    "fact_id": args.fact_id,
                    "meaning": args.meaning,
                    "renderings": renderings,
                    "tags": args.tag,
                    "provenance": args.provenance,
                    "effective_dates": args.dates,
                    "replaces": args.replaces,
                    "resume_style": args.style,
                },
                canonical=args.canonical,
                reason=args.reason,
            )
        )
    elif args.fact_command == "capture":
        _print(
            knowledge.capture_claim_fact(
                args.application_id,
                args.claim_id,
                source=args.source,
                fact_id=args.fact_id,
                meaning=args.meaning,
                tags=args.tag,
                english=args.en,
                hebrew=args.he,
                provenance=args.provenance,
                effective_dates=args.dates,
                replaces=args.replaces,
                canonical=args.canonical,
                reason=args.reason,
            )
        )
    elif args.fact_command in {"confirm", "promote"}:
        target = FactStatus.CONFIRMED if args.fact_command == "confirm" else FactStatus.CANONICAL
        if not args.confirm:
            print(
                f"ERROR: promotion to {target.value} requires explicit --confirm",
                file=sys.stderr,
            )
            return 2
        _print(
            knowledge.promote_fact(
                args.fact_id,
                target.value,
                explicitly_confirmed=True,
                reason=args.reason,
            )
        )
    elif args.fact_command == "attach":
        _print(knowledge.attach_fact(args.fact_id, args.profile, args.section, pin=args.pin))
    return 0


def generic_reconcile(workspace: Workspace, repository: ApplicationRepository) -> dict[str, Any]:
    problems = repository.integrity_check()
    checked = 0
    for row in repository.artifact_inventory():
        checked += 1
        path = workspace.root / row["path"]
        verification = verify_payload(path, row["content_hash"])
        if verification == "missing":
            problems.append(f"missing artifact: {row['path']}")
        elif verification == "tampered":
            problems.append(f"artifact hash mismatch: {row['path']}")
    return {"passed": not problems, "artifact_versions_checked": checked, "problems": problems}


def _resolve_root(args: argparse.Namespace) -> tuple[Path, Any]:
    """The selected root plus the resolved configuration behind it.

    `--repo` stays accepted because v1 scripts pass it, but it is an alias with
    a warning rather than a second concept: one Workspace selection, resolved
    through CLI > environment > Workspace config > default.
    """
    if args.repo is not None:
        print("WARNING: --repo is deprecated; use --workspace", file=sys.stderr)
    selected = args.workspace or args.repo
    config = resolve_config(cli={"workspace": selected, "database": args.db}, env=os.environ)
    root = Path(config.get("workspace") or _repo_root()).resolve()
    return root, config


def workspace_command(
    root: Path,
    config: Any,
    args: argparse.Namespace,
    *,
    opened: Workspace | None = None,
) -> int:
    if args.workspace_command == "init":
        created = create_workspace(
            root,
            purpose=args.purpose,
            data_class=args.data_class,
            knowledge_source=args.knowledge_from.resolve() if args.knowledge_from else None,
        )
        _print(
            {**created.describe(), "installation_id": created.installation_id(), "created": True}
        )
        return 0
    if args.workspace_command == "status":
        opened = opened or load_workspace(root)
        _print(
            {
                **opened.describe(),
                "installation_id": opened.installation_id(),
                "database": str(opened.database_path),
                "schema_version": current_schema_version(opened.database_path),
                "configuration": config.describe(),
            }
        )
        return 0
    source = LegacyV1Source(args.source.resolve())
    inventory = source.inventory()
    _print({**inventory.describe(), "read_only": True, "marker_written": False})
    return 0


@dataclass
class CommandContext:
    """What one command was given, opened as far as that command needs.

    A command's stage is what it may touch: `workspace init` runs before a
    Workspace exists, `migrate` verifies one without opening its database,
    `init` creates the schema the services would otherwise expect, and every
    other command gets built services. Building only up to the stage keeps
    each command's fail-closed order the same as before the split.
    """

    args: argparse.Namespace
    root: Path
    config: Any
    workspace: Workspace | None = None
    database_path: Path | None = None
    services: Services | None = None

    @property
    def opened_workspace(self) -> Workspace:
        assert self.workspace is not None
        return self.workspace

    @property
    def built_services(self) -> Services:
        assert self.services is not None
        return self.services

    @property
    def repository(self) -> ApplicationRepository:
        return self.built_services.repository

    @property
    def opened_database_path(self) -> Path:
        assert self.database_path is not None
        return self.database_path


Handler = Callable[[CommandContext], int]

_HANDLERS: dict[str, tuple[str, Handler]] = {}


def _command(name: str, *, needs: str = "services") -> Callable[[Handler], Handler]:
    """Register the handler for one top-level command and the stage it needs."""

    def register(handler: Handler) -> Handler:
        _HANDLERS[name] = (needs, handler)
        return handler

    return register


def _workspace_config(args: argparse.Namespace, workspace: Workspace) -> Any:
    return resolve_config(
        cli={"workspace": args.workspace or args.repo, "database": args.db},
        env=os.environ,
        workspace_root=workspace.root,
    )


def _build_context(args: argparse.Namespace, root: Path, config: Any, needs: str) -> CommandContext:
    context = CommandContext(args=args, root=root, config=config)
    if needs == "root":
        return context
    # Every remaining command is a normal v2 command, so it opens the
    # Workspace fail-closed before it touches state.
    context.workspace = load_workspace(root)
    context.config = _workspace_config(args, context.workspace)
    if needs == "workspace":
        return context
    db_override = context.config.get("database")
    context.database_path = (
        resolve_within(context.workspace.state_root, db_override)
        if db_override
        else context.workspace.database_path
    )
    if needs == "database":
        return context
    context.services = build_services(context.workspace, database_path=context.database_path)
    return context


@_command("workspace", needs="root")
def _workspace(context: CommandContext) -> int:
    args = context.args
    if args.workspace_command != "status":
        return workspace_command(context.root, context.config, args)
    workspace = load_workspace(context.root)
    return workspace_command(
        context.root, _workspace_config(args, workspace), args, opened=workspace
    )


@_command("migrate", needs="workspace")
def _migrate(context: CommandContext) -> int:
    args = context.args
    if args.migration_command == "verify-source":
        report = verify_source(context.root)
    else:
        report = retrospective_verify_migration(context.root)
    _print(report)
    return 0 if report["passed"] else 1


@_command("init", needs="database")
def _init(context: CommandContext) -> int:
    database_path = context.opened_database_path
    initialize(database_path)
    _print({"database": str(database_path), "schema_initialized": True})
    return 0


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
    analysed = context.built_services.analysis.analyze(
        AnalyzeCommand(
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
    )
    _print(
        {
            "analysis_id": analysed.analysis_id,
            "selection_plan_id": analysed.selection_plan_id,
            "analysis": analysed.analysis.model_dump(mode="json"),
        }
    )
    return 0


@_command("draft")
def _draft(context: CommandContext) -> int:
    args = context.args
    services = context.built_services
    drafted = services.drafts.draft(
        DraftCommand(
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
    )
    paths = services.artifacts.working_paths(args.application_id)
    _print(
        {
            "markdown": str(paths.markdown),
            "claim_manifest": str(paths.manifest),
            "validation": drafted.validation.model_dump(mode="json"),
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
    approved = services.drafts.approve(context.args.application_id)
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
    rendered = services.rendering.render(application_id)
    pdf_record = context.repository.latest_artifact_version(application_id, "resume_pdf")
    pdf_metadata = json.loads(pdf_record.get("metadata_json") or "{}")
    _print(
        {
            "pdf": str(services.artifacts.resolve(pdf_record["path"])),
            "filename": pdf_metadata.get("recruiter_filename"),
            "ready_validation": rendered.validation.model_dump(mode="json"),
        }
    )
    return 0 if rendered.validation.passed else 1


@_command("ready")
def _ready(context: CommandContext) -> int:
    report = context.built_services.rendering.ready_report(context.args.application_id)
    _print(report.model_dump(mode="json"))
    return 0 if report.passed else 1


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


@_command("link-claim")
def _link_claim(context: CommandContext) -> int:
    args = context.args
    services = context.built_services
    edited = services.drafts.link_claim(args.application_id, args.claim_id, args.text, args.fact_id)
    return _print_claim_edit(services, args.application_id, edited)


@_command("export")
def _export(context: CommandContext) -> int:
    exported = export_csv(
        context.built_services.queries.list_applications(), context.args.output.resolve()
    )
    _print(
        {
            "csv": str(exported),
            "metadata": str(exported.with_suffix(exported.suffix + ".meta.json")),
            "export_schema_version": EXPORT_SCHEMA_VERSION,
        }
    )
    return 0


@_command("reconcile")
def _reconcile(context: CommandContext) -> int:
    services = context.built_services
    report = generic_reconcile(context.opened_workspace, context.repository)
    fact_lifecycle = services.knowledge_lifecycle.reconcile_facts()
    report["fact_lifecycle"] = fact_lifecycle.model_dump(mode="json")
    report["passed"] = report["passed"] and fact_lifecycle.passed
    _print(report)
    return 0 if report["passed"] else 1


@_command("fact")
def _fact(context: CommandContext) -> int:
    return fact_command(context.built_services.knowledge_lifecycle, context.args)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        root, config = _resolve_root(args)
    except (WorkspaceError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    needs, handler = _HANDLERS[args.command]
    try:
        return handler(_build_context(args, root, config, needs))
    except (
        ValueError,
        KeyError,
        FileNotFoundError,
        WorkflowError,
        MigrationSafetyError,
        WorkspaceError,
        LegacySourceError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
