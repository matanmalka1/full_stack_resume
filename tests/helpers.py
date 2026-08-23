from __future__ import annotations

import io
import os
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from cv_engine.application.commands import ApproveDraftCommand, ValidateDraftCommand
from cv_engine.cli import main as cli_main
from cv_engine.domain.draft_markdown import parse_draft
from cv_engine.infrastructure.artifacts import FilesystemArtifactStore
from cv_engine.runtime.composition import Services
from cv_engine.runtime.workspace import load_workspace


def artifact_store(root: Path) -> FilesystemArtifactStore:
    """The real artifact adapter for a test Workspace.

    Tests that need a draft on disk go through the same adapter the product
    uses, so no test carries its own copy of the storage layout.
    """
    return FilesystemArtifactStore(load_workspace(root))


def store_draft(root: Path, draft):
    """Write a working draft and return its Markdown path and exact text."""
    stored = artifact_store(root).write_working_draft(draft)
    return stored.paths.markdown, stored.markdown


ACCOUNT_MANAGER_JOB = (
    "Account Manager responsible for retention, portfolio growth, negotiation, "
    "and customer relationships."
)

# Hebrew, low confidence, one hard gap and one warning gap: the deterministic
# classifier requires approval here, so it exposes anything a provider could
# quietly relax.
AMBIGUOUS_HEBREW_JOB = (
    "דרוש מנהל לקוחות עם ניסיון בפיתוח עסקי ובניהול תיק לקוחות מול ארגונים גדולים. "
    "התפקיד כולל אחריות על שימור, גיוס לקוחות חדשים והובלת תהליכי מכירה מורכבים. "
    "דרישות: account manager, business development, Salesforce, must have direct saas sales."
)

PAYME_TECH_SALES_JOB = (
    "FinTech platform for small businesses. Strategic Partnerships Sales Manager "
    "responsible for new partner acquisition and outbound Sales to website builders, "
    "CRMs, marketplaces, and software providers that can embed financial products. "
    "Engage prospects by phone and email, understand their needs, offer tailored "
    "solutions, pitch the service, guide the Sales process through closing, onboard "
    "customers, and maintain Sales progress and follow-up tasks in our CRM system. "
    "Prefer inside Sales experience in a SaaS or tech-related industry."
)


def validate_active_draft(services: Services, application_id: str):
    """Validate the Application's active draft and return the run result.

    The v2 command takes a WorkingDraft ID and an exact edit version, so
    resolving "the active one" is the caller's job. Every test that used to
    call `validate_working(application_id)` resolves it the same way here
    rather than each writing its own two lines.
    """
    working = services.repository.active_working_draft(application_id)
    return services.drafts.validate_draft(
        ValidateDraftCommand(
            working_draft_id=working.id,
            expected_edit_version=working.edit_version,
        )
    )


def approve_active_draft(services: Services, application_id: str, *, revision_id=None):
    """Validate, then approve exactly what that run passed.

    This is what `cv approve` does at the CLI boundary, and it is what every
    caller must now do: approval no longer validates for itself, so a test that
    approves has to obtain the run first - which is the whole point of the
    change.
    """
    validated = validate_active_draft(services, application_id)
    return services.drafts.approve_draft(
        ApproveDraftCommand(
            working_draft_id=validated.working_draft_id,
            expected_edit_version=validated.edit_version,
            validation_run_id=validated.validation_run_id,
        ),
        revision_id=revision_id,
    )


def working_claim(services: Services, application_id: str, fact_id: str):
    manifest = services.artifacts.working_paths(application_id).manifest
    draft = parse_draft(manifest.read_text(encoding="utf-8"))
    return next(
        claim for section in draft.sections for claim in section.claims if fact_id in claim.fact_ids
    )


def exact_fact_claim(draft, fact_ids: list[str]):
    return next(
        claim
        for section in draft.sections
        for claim in section.claims
        if claim.fact_ids == fact_ids
    )


def claim_by_id(draft, claim_id: str):
    return next(
        claim
        for section in draft.sections
        for claim in section.claims
        if claim.claim_id == claim_id
    )


def artifact_version_and_path(
    services: Services,
    application_id: str,
    artifact_type: str,
    lifecycle_status: str,
):
    version = services.repository.latest_artifact_version(
        application_id, artifact_type, lifecycle_status
    )
    return version, services.artifacts.resolve(version["path"])


def passing_migration_test_runner(root: Path) -> Path:
    return root / "data/migration/migration-tests.json"


@dataclass(frozen=True)
class CliRun:
    """What a CLI invocation produced: the same three fields a process yields."""

    returncode: int
    stdout: str
    stderr: str


def run_cli(*args: str, env: dict[str, str] | None = None) -> CliRun:
    """Run the CLI in this process with the argv `python -m cv_engine.cli` takes.

    The CLI has two exit paths — a returned exit code, and argparse raising
    SystemExit on a parser error — and a real process collapses both into one
    status. This collapses them the same way, so a test reads one result
    whether the failure came from a command or from the parser.

    Use this for CLI behavior. A test whose subject is the process boundary
    itself — state surviving between runs, the module entry point — runs the
    real process instead.
    """
    out, err = io.StringIO(), io.StringIO()
    with patch.dict(os.environ, env or {}):
        with redirect_stdout(out), redirect_stderr(err):
            try:
                code = cli_main(list(args))
            except SystemExit as exc:
                if exc.code is None:
                    code = 0
                elif isinstance(exc.code, int):
                    code = exc.code
                else:
                    code = 1
    return CliRun(code, out.getvalue(), err.getvalue())
