from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any

from .infrastructure.db import Repository, connect, initialize
from .infrastructure.legacy_source import LegacySourceError, LegacyV1Source
from .runtime.config import resolve_config
from .runtime.workspace import Workspace, WorkspaceError, create_workspace, load_workspace
from .infrastructure.migration import (
    MigrationSafetyError,
    apply_migration,
    create_snapshot,
    dry_run_migration,
    reconcile_migration,
    retrospective_verify_migration,
    run_migration_tests,
    verify_snapshot,
    write_inventory,
)
from .domain.facts import FACT_SOURCE_NAMES
from .domain.models import ApplicationStatus, FactStatus
from .util import sha256_file, utc_now
from .application.services import WorkflowError
from .compat import Engine, resolve_job_analysis_id, resolve_job_snapshot_id
from .runtime.composition import build_services


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def _job_text(args: argparse.Namespace) -> str:
    if getattr(args, "job_file", None):
        return Path(args.job_file).read_text(encoding="utf-8")
    if getattr(args, "job_text", None):
        return args.job_text
    raise ValueError("one of --job-file or --job-text is required")


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
    workspace_init = workspace_sub.add_parser("init", help="create an isolated Workspace and its marker")
    workspace_init.add_argument("--purpose", choices=["development", "test", "live"], default="development")
    workspace_init.add_argument("--data-class", choices=["copy", "test", "live"], default="copy")
    workspace_init.add_argument(
        "--knowledge-from",
        type=Path,
        help="copy base/profiles/rendering/config/ai from this directory into the new Workspace",
    )
    workspace_sub.add_parser("status", help="show Workspace identity, roots, and resolved configuration")
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
    # so the compatibility resolver fills it in when the flag is absent.
    analyze.add_argument("--job-snapshot", dest="job_snapshot", default=None)

    draft = sub.add_parser("draft", help="create or update the active working draft")
    draft.add_argument("application_id")
    draft.add_argument("--job-analysis", dest="job_analysis", default=None)

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
        choices=[item.value for item in ApplicationStatus if item is not ApplicationStatus.READY],
        help="ready is engine-owned and cannot be set manually; it is reached only via the render pipeline",
    )
    status.add_argument("--reason", default="manual CLI transition")
    action = sub.add_parser("action", help="set or clear the next action")
    action.add_argument("application_id")
    action.add_argument("--next-action")
    action.add_argument("--date")
    edit = sub.add_parser("edit-claim", help="classify and save a canonical, derived, composite, or pending claim edit")
    edit.add_argument("application_id")
    edit.add_argument("claim_id")
    edit_mode = edit.add_mutually_exclusive_group(required=True)
    edit_mode.add_argument("--text")
    edit_mode.add_argument("--template", choices=["canonical-renderings"])
    edit.add_argument("--template-version", default="1.0.0")
    edit.add_argument("--fact-id", action="append", required=True)
    sync = sub.add_parser("sync-draft", help="extract marked manual Markdown edits and classify their claims")
    sync.add_argument("application_id")
    link = sub.add_parser("link-claim", help="compatibility alias for a text-based claim edit")
    link.add_argument("application_id")
    link.add_argument("claim_id")
    link.add_argument("--text", required=True)
    link.add_argument("--fact-id", action="append", required=True)
    export = sub.add_parser("export", help="export application data to CSV")
    export.add_argument("output", type=Path)
    sub.add_parser("reconcile", help="reconcile SQLite references, artifact hashes, and the fact lifecycle")

    fact = sub.add_parser("fact", help="manage the pending -> confirmed -> canonical fact lifecycle")
    fact_sub = fact.add_subparsers(dest="fact_command", required=True)
    fact_list = fact_sub.add_parser("list", help="list stored facts and their lifecycle status")
    fact_list.add_argument("--status", choices=[item.value for item in FactStatus])
    fact_show = fact_sub.add_parser("show", help="inspect one fact and its lifecycle events")
    fact_show.add_argument("fact_id")
    fact_add = fact_sub.add_parser("add", help="create a new fact; pending unless explicitly confirmed")
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
    fact_confirm.add_argument("--confirm", action="store_true", help="required explicit confirmation")
    fact_confirm.add_argument("--reason", default="")
    fact_promote = fact_sub.add_parser("promote", help="promote confirmed -> canonical")
    fact_promote.add_argument("fact_id")
    fact_promote.add_argument("--confirm", action="store_true", help="required explicit confirmation")
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

    migrate = sub.add_parser("migrate", help="guarded one-time legacy migration")
    migrate_sub = migrate.add_subparsers(dest="migration_command", required=True)
    migrate_sub.add_parser("inventory")
    migrate_sub.add_parser("snapshot")
    verify = migrate_sub.add_parser("verify-snapshot")
    verify.add_argument("--snapshot", type=Path, required=True)
    migrate_sub.add_parser("test")
    dry_run = migrate_sub.add_parser("dry-run")
    dry_run.add_argument("--snapshot", type=Path, required=True)
    apply = migrate_sub.add_parser("apply")
    apply.add_argument("--snapshot", type=Path, required=True)
    verify_live = migrate_sub.add_parser("verify-live", help="read-only semantic verification of the completed migration")
    verify_live.add_argument("--snapshot", type=Path, required=True)
    migrate_sub.add_parser("reconcile")
    return parser


EXPORT_SCHEMA_VERSION = "2.0"


def export_csv(repository: Repository, output: Path) -> Path:
    """Export applications with an explicit, versioned schema.

    The v1 export had no version marker, so a consumer could not tell which
    columns to expect. No such consumer was found in this repository, so the
    v2 export keeps the same columns and records the schema beside them rather
    than inventing a compatibility mode nothing asked for.
    """
    rows = repository.list_applications()
    fields = [
        "id", "company", "target_role", "normalized_role", "source_url", "language",
        "track", "profile", "emphasis", "classification_confidence", "fit_level",
        "current_status", "last_contact_date", "next_action", "next_action_date",
        "notes", "source", "created_at", "updated_at",
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
        _print(knowledge.list_facts(args.status))
    elif args.fact_command == "show":
        _print(knowledge.show_fact(args.fact_id))
    elif args.fact_command == "history":
        _print(knowledge.fact_history(args.fact_id))
    elif args.fact_command == "add":
        renderings = {"en": args.en}
        if args.he:
            renderings["he"] = args.he
        _print(knowledge.add_fact(
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
        ))
    elif args.fact_command == "capture":
        _print(knowledge.capture_claim_fact(
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
        ))
    elif args.fact_command in {"confirm", "promote"}:
        target = FactStatus.CONFIRMED if args.fact_command == "confirm" else FactStatus.CANONICAL
        if not args.confirm:
            print(
                f"ERROR: promotion to {target.value} requires explicit --confirm",
                file=sys.stderr,
            )
            return 2
        _print(knowledge.promote_fact(
            args.fact_id,
            target.value,
            explicitly_confirmed=True,
            reason=args.reason,
        ))
    elif args.fact_command == "attach":
        _print(knowledge.attach_fact(args.fact_id, args.profile, args.section, pin=args.pin))
    return 0


def generic_reconcile(workspace: Workspace, repository: Repository) -> dict[str, Any]:
    problems = repository.integrity_check()
    checked = 0
    for row in repository.artifact_inventory():
        checked += 1
        path = workspace.root / row["path"]
        if not path.is_file():
            problems.append(f"missing artifact: {row['path']}")
        elif sha256_file(path) != row["content_hash"]:
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
    return root, resolve_config(
        cli={"workspace": selected, "database": args.db},
        env=os.environ,
        workspace_root=root,
    )


def workspace_command(root: Path, config: Any, args: argparse.Namespace) -> int:
    if args.workspace_command == "init":
        created = create_workspace(
            root,
            purpose=args.purpose,
            data_class=args.data_class,
            knowledge_source=args.knowledge_from.resolve() if args.knowledge_from else None,
        )
        _print({**created.describe(), "installation_id": created.installation_id(), "created": True})
        return 0
    if args.workspace_command == "status":
        opened = load_workspace(root)
        _print({
            **opened.describe(),
            "installation_id": opened.installation_id(),
            "database": str(opened.database_path),
            "configuration": config.describe(),
        })
        return 0
    source = LegacyV1Source(args.source.resolve())
    inventory = source.inventory()
    _print({**inventory.describe(), "read_only": True, "marker_written": False})
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        root, config = _resolve_root(args)
    except (WorkspaceError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    db_override = config.get("database")
    try:
        if args.command == "workspace":
            return workspace_command(root, config, args)
        if args.command == "migrate":
            if args.migration_command == "inventory":
                path = write_inventory(root)
                _print({"inventory": str(path), "passed": True})
            elif args.migration_command == "snapshot":
                path = create_snapshot(root)
                _print({"snapshot": str(path), "passed": True})
            elif args.migration_command == "verify-snapshot":
                report = verify_snapshot(args.snapshot.resolve())
                _print(report)
                return 0 if report["passed"] else 1
            elif args.migration_command == "test":
                path = run_migration_tests(root)
                _print(json.loads(path.read_text(encoding="utf-8")))
            elif args.migration_command == "dry-run":
                path = dry_run_migration(root, args.snapshot.resolve())
                _print(json.loads(path.read_text(encoding="utf-8")))
            elif args.migration_command == "apply":
                path = apply_migration(root, args.snapshot.resolve())
                _print(json.loads(path.read_text(encoding="utf-8")))
            elif args.migration_command == "verify-live":
                report = retrospective_verify_migration(root, args.snapshot.resolve())
                _print(report)
                return 0 if report["passed"] else 1
            elif args.migration_command == "reconcile":
                report = reconcile_migration(root)
                _print(report)
                return 0 if report["passed"] else 1
            return 0

        # Every remaining command is a normal v2 command, so it opens the
        # Workspace fail-closed before it touches state.
        workspace = load_workspace(root)
        db_path = Path(db_override).resolve() if db_override else workspace.database_path
        if args.command == "init":
            initialize(db_path)
            _print({"database": str(db_path), "schema_initialized": True})
            return 0
        services = build_services(workspace, database_path=db_path)
        repository = services.repository
        engine = Engine(workspace, services=services)
        if args.command == "ingest":
            ingested = services.applications.ingest(args.company, args.role, _job_text(args), args.url)
            _print({
                "application_id": ingested.application_id,
                "job_snapshot_id": ingested.job_snapshot_id,
            })
        elif args.command == "analyze":
            analysed = services.analysis.analyze(
                args.application_id,
                args.job_snapshot or resolve_job_snapshot_id(repository, args.application_id),
                track=args.track,
                profile=args.profile,
                emphasis=args.emphasis,
                language=args.language,
                accept_low_fit=args.accept_low_fit,
                provider=args.provider,
                model=args.model,
            )
            _print({
                "analysis_id": analysed.analysis_id,
                "analysis": analysed.analysis.model_dump(mode="json"),
            })
        elif args.command == "draft":
            drafted = services.drafts.draft(
                args.application_id,
                args.job_analysis or resolve_job_analysis_id(repository, args.application_id),
            )
            _print({
                "markdown": str(drafted.markdown),
                "claim_manifest": str(drafted.manifest),
                "validation": drafted.validation.model_dump(mode="json"),
                "review_required": True,
            })
        elif args.command == "validate":
            report = services.drafts.validate_working(args.application_id)
            _print(report.model_dump(mode="json"))
            return 0 if report.passed else 1
        elif args.command == "approve":
            approved = services.drafts.approve(args.application_id)
            _print({
                "version": approved.version,
                "directory": approved.directory,
                "decision_record_id": approved.decision_record_id,
            })
        elif args.command == "render":
            rendered = services.rendering.render(args.application_id)
            _print({
                "pdf": str(rendered.pdf),
                "ready_validation": rendered.validation.model_dump(mode="json"),
            })
            return 0 if rendered.validation.passed else 1
        elif args.command == "ready":
            report = services.rendering.ready_report(args.application_id)
            _print(report.model_dump(mode="json"))
            return 0 if report.passed else 1
        elif args.command == "fast":
            _print(engine.fast(
                args.company, args.role, _job_text(args), url=args.url,
                track=args.track, profile=args.profile, emphasis=args.emphasis,
                language=args.language, accept_low_fit=args.accept_low_fit,
            ))
        elif args.command == "list":
            _print(repository.list_applications())
        elif args.command == "show":
            app = repository.get_application(args.application_id)
            app["latest_snapshot"] = repository.latest_snapshot(args.application_id)
            try:
                app["latest_analysis"] = repository.latest_analysis(args.application_id)[1].model_dump(mode="json")
            except KeyError:
                app["latest_analysis"] = None
            _print(app)
        elif args.command == "versions":
            _print(repository.artifact_versions(args.application_id))
        elif args.command == "decision":
            record = repository.latest_decision(args.application_id)
            record["structured"] = json.loads(record.pop("structured_json"))
            _print(record)
        elif args.command == "status":
            if args.status == ApplicationStatus.APPLIED.value:
                submitted = services.tracking.submit(args.application_id, args.reason)
                _print({
                    "application_id": submitted.application_id,
                    "pdf_artifact_version_id": submitted.pdf_artifact_version_id,
                    **submitted.application,
                })
            else:
                repository.transition_status(args.application_id, args.status, args.reason)
                _print(repository.get_application(args.application_id))
        elif args.command == "action":
            repository.set_next_action(args.application_id, args.next_action, args.date)
            _print(repository.get_application(args.application_id))
        elif args.command == "edit-claim":
            edited = services.drafts.edit_claim(
                args.application_id,
                args.claim_id,
                args.fact_id,
                text=args.text,
                template_id=args.template,
                template_version=args.template_version,
            )
            _print({
                "markdown": str(edited.markdown),
                "validation": edited.validation.model_dump(mode="json"),
            })
            return 0 if edited.validation.passed else 1
        elif args.command == "sync-draft":
            edited = services.drafts.sync_working_claims(args.application_id)
            _print({
                "markdown": str(edited.markdown),
                "validation": edited.validation.model_dump(mode="json"),
            })
            return 0 if edited.validation.passed else 1
        elif args.command == "link-claim":
            edited = services.drafts.link_claim(args.application_id, args.claim_id, args.text, args.fact_id)
            _print({
                "markdown": str(edited.markdown),
                "validation": edited.validation.model_dump(mode="json"),
            })
            return 0 if edited.validation.passed else 1
        elif args.command == "export":
            exported = export_csv(repository, args.output.resolve())
            _print({
                "csv": str(exported),
                "metadata": str(exported.with_suffix(exported.suffix + ".meta.json")),
                "export_schema_version": EXPORT_SCHEMA_VERSION,
            })
        elif args.command == "reconcile":
            report = generic_reconcile(workspace, repository)
            report["fact_lifecycle"] = services.knowledge_lifecycle.reconcile_facts()
            report["passed"] = report["passed"] and report["fact_lifecycle"]["passed"]
            _print(report)
            return 0 if report["passed"] else 1
        elif args.command == "fact":
            return fact_command(services.knowledge_lifecycle, args)
        return 0
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
