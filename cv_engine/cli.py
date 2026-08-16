from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

from .db import Repository, connect, initialize
from .migration import (
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
from .models import ApplicationStatus
from .util import sha256_file
from .workflow import Engine, WorkflowError


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cv", description="Multi-track fact-safe CV engine")
    parser.add_argument("--repo", type=Path, default=_repo_root())
    parser.add_argument("--db", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="initialize the v1 SQLite schema")
    ingest = sub.add_parser("ingest", help="create an application and immutable job snapshot")
    _add_job_input(ingest)

    analyze = sub.add_parser("analyze", help="classify Track/Profile/Emphasis and fit")
    analyze.add_argument("application_id")
    _add_overrides(analyze)
    analyze.add_argument("--provider", choices=["deterministic", "openai"], default="deterministic")
    analyze.add_argument("--model", default="gpt-5.6")

    for name, help_text in [
        ("draft", "create or update the active working draft"),
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
    status.add_argument("status", choices=[item.value for item in ApplicationStatus])
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
    sub.add_parser("reconcile", help="reconcile SQLite references and artifact hashes")

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


def export_csv(repository: Repository, output: Path) -> Path:
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
    return output


def generic_reconcile(root: Path, repository: Repository) -> dict[str, Any]:
    problems = repository.integrity_check()
    checked = 0
    with connect(repository.path) as connection:
        rows = connection.execute("SELECT path, content_hash FROM artifact_versions").fetchall()
    for row in rows:
        checked += 1
        path = root / row["path"]
        if not path.is_file():
            problems.append(f"missing artifact: {row['path']}")
        elif sha256_file(path) != row["content_hash"]:
            problems.append(f"artifact hash mismatch: {row['path']}")
    return {"passed": not problems, "artifact_versions_checked": checked, "problems": problems}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = args.repo.resolve()
    db_path = args.db.resolve() if args.db else root / "data/applications.sqlite3"
    try:
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

        if args.command == "init":
            initialize(db_path)
            _print({"database": str(db_path), "schema_initialized": True})
            return 0
        engine = Engine(root, db_path)
        if args.command == "ingest":
            app_id, snapshot_id = engine.ingest(args.company, args.role, _job_text(args), args.url)
            _print({"application_id": app_id, "job_snapshot_id": snapshot_id})
        elif args.command == "analyze":
            analysis_id, analysis = engine.analyze(
                args.application_id,
                track=args.track,
                profile=args.profile,
                emphasis=args.emphasis,
                language=args.language,
                accept_low_fit=args.accept_low_fit,
                provider=args.provider,
                model=args.model,
            )
            _print({"analysis_id": analysis_id, "analysis": analysis.model_dump(mode="json")})
        elif args.command == "draft":
            markdown, manifest, report = engine.draft(args.application_id)
            _print({"markdown": str(markdown), "claim_manifest": str(manifest), "validation": report.model_dump(mode="json"), "review_required": True})
        elif args.command == "validate":
            report = engine.validate_working(args.application_id)
            _print(report.model_dump(mode="json"))
            return 0 if report.passed else 1
        elif args.command == "approve":
            _print(engine.approve(args.application_id))
        elif args.command == "render":
            pdf, report = engine.render(args.application_id)
            _print({"pdf": str(pdf), "ready_validation": report.model_dump(mode="json")})
            return 0 if report.passed else 1
        elif args.command == "ready":
            _print(engine.ready_report(args.application_id).model_dump(mode="json"))
        elif args.command == "fast":
            _print(engine.fast(
                args.company, args.role, _job_text(args), url=args.url,
                track=args.track, profile=args.profile, emphasis=args.emphasis,
                language=args.language, accept_low_fit=args.accept_low_fit,
            ))
        elif args.command == "list":
            _print(engine.repo.list_applications())
        elif args.command == "show":
            app = engine.repo.get_application(args.application_id)
            app["latest_snapshot"] = engine.repo.latest_snapshot(args.application_id)
            try:
                app["latest_analysis"] = engine.repo.latest_analysis(args.application_id)[1].model_dump(mode="json")
            except KeyError:
                app["latest_analysis"] = None
            _print(app)
        elif args.command == "versions":
            _print(engine.repo.artifact_versions(args.application_id))
        elif args.command == "decision":
            record = engine.repo.latest_decision(args.application_id)
            record["structured"] = json.loads(record.pop("structured_json"))
            _print(record)
        elif args.command == "status":
            engine.repo.transition_status(args.application_id, args.status, args.reason)
            _print(engine.repo.get_application(args.application_id))
        elif args.command == "action":
            engine.repo.set_next_action(args.application_id, args.next_action, args.date)
            _print(engine.repo.get_application(args.application_id))
        elif args.command == "edit-claim":
            markdown, report = engine.edit_claim(
                args.application_id,
                args.claim_id,
                args.fact_id,
                text=args.text,
                template_id=args.template,
                template_version=args.template_version,
            )
            _print({"markdown": str(markdown), "validation": report.model_dump(mode="json")})
            return 0 if report.passed else 1
        elif args.command == "sync-draft":
            markdown, report = engine.sync_working_claims(args.application_id)
            _print({"markdown": str(markdown), "validation": report.model_dump(mode="json")})
            return 0 if report.passed else 1
        elif args.command == "link-claim":
            markdown, report = engine.link_claim(args.application_id, args.claim_id, args.text, args.fact_id)
            _print({"markdown": str(markdown), "validation": report.model_dump(mode="json")})
            return 0 if report.passed else 1
        elif args.command == "export":
            _print({"csv": str(export_csv(engine.repo, args.output.resolve()))})
        elif args.command == "reconcile":
            report = generic_reconcile(root, engine.repo)
            _print(report)
            return 0 if report["passed"] else 1
        return 0
    except (ValueError, KeyError, FileNotFoundError, WorkflowError, MigrationSafetyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
