from __future__ import annotations

from pathlib import Path

import pytest
from helpers import ACCOUNT_MANAGER_JOB, approve_active_draft, validate_active_draft
from helpers import working_claim as _working_claim

from cv_engine.application.commands import (
    IngestCommand,
)
from cv_engine.application.errors import StateConflict, WorkflowError
from cv_engine.domain.draft_markdown import parse_draft, serialize_markdown
from cv_engine.infrastructure.artifacts import FilesystemArtifactStore
from cv_engine.runtime.paths import AppPaths


def test_csv_export_declares_its_schema_version(services, tmp_path: Path) -> None:
    import json as _json

    from cv_engine.application.maintenance import EXPORT_SCHEMA_VERSION
    from cv_engine.infrastructure.exports import export_csv

    ingested = services.applications.ingest(
        IngestCommand(
            company="Acme", target_role="Developer", job_text="Python developer role", client="web"
        )
    )
    app_id = ingested.application_id
    output = export_csv(services.queries.list_applications(), tmp_path / "applications.csv")
    text = output.read_text(encoding="utf-8")
    assert "current_status" in text
    assert app_id in text

    metadata = _json.loads(
        output.with_suffix(output.suffix + ".meta.json").read_text(encoding="utf-8")
    )
    assert metadata["export_schema_version"] == EXPORT_SCHEMA_VERSION
    assert metadata["row_count"] == 1
    assert metadata["columns"][0] == "id"
    assert "current_status" in metadata["columns"]


def test_filesystem_working_draft_unconditionally_overwrites_the_projection(
    app_paths: AppPaths,
    draft_factory,
) -> None:
    application_id = "overwrite-projection"
    first = draft_factory(
        ACCOUNT_MANAGER_JOB,
        application_id=application_id,
    ).draft
    replacement = draft_factory(
        "Python backend developer API React",
        application_id=application_id,
    ).draft
    store = FilesystemArtifactStore(app_paths)

    first_stored = store.write_working_draft(first)
    first_markdown = first_stored.paths.markdown.read_text(encoding="utf-8")
    replacement_stored = store.write_working_draft(replacement)

    assert replacement_stored.paths == first_stored.paths
    assert replacement_stored.paths.markdown.read_text(encoding="utf-8") == (
        serialize_markdown(replacement)
    )
    assert (
        parse_draft(replacement_stored.paths.manifest.read_text(encoding="utf-8")).profile
        == replacement.profile
    )
    assert first_markdown != replacement_stored.markdown


def test_validate_reports_on_the_stored_draft_not_the_edited_file(
    drafted_application,
) -> None:
    """`validate` describes what storage holds, which is what approval will freeze.

    A hand edit to the projection file is not absorbed by validating: the report
    would otherwise vouch for wording the database never saw. Editing the file
    by hand is no longer a supported path, and the guarantee that matters is
    that nothing quietly adopts such an edit.
    """
    setup = drafted_application("Manual Edit")
    services, app_id = setup
    markdown = setup.markdown
    claim = _working_claim(services, app_id, "sales.metric.performance")
    markdown.write_text(
        markdown.read_text(encoding="utf-8").replace(claim.text, claim.text.rstrip("."), 1),
        encoding="utf-8",
    )

    report = validate_active_draft(services, app_id).report

    assert report.passed, report.model_dump()
    assert _working_claim(services, app_id, "sales.metric.performance").claim_type == "canonical"


def test_approval_refuses_while_the_projection_holds_an_unimported_edit(
    drafted_application,
) -> None:
    """The data-loss guard: approval rebuilds the projection from the database.

    An unimported file edit would be destroyed without a word, so approval
    refuses rather than overwriting it. The refusal is the whole protection -
    it names the two ways forward and touches nothing.
    """
    setup = drafted_application("Unimported Edit")
    services, app_id = setup
    markdown = setup.markdown
    claim = _working_claim(services, app_id, "sales.metric.performance")
    markdown.write_text(
        markdown.read_text(encoding="utf-8").replace(
            claim.text,
            "Delivered 30% improvement in direct SaaS Sales.",
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(StateConflict) as refusal:
        approve_active_draft(services, app_id)

    assert "differs from the stored draft" in str(refusal.value)
    assert services.repository.approved_revisions(app_id) == []
    # The edit is never touched: refusing is what keeps it recoverable.
    assert "direct SaaS Sales" in markdown.read_text(encoding="utf-8")


def test_style_safe_composite_edit_joins_two_canonical_facts(drafted_application) -> None:
    """Editing one claim onto two facts through a template makes it composite.

    The subject is the edit, not any one caller: `PATCH /working-drafts/{id}`
    and the draft service reach the same method, so this drives the service.
    """
    services, app_id = drafted_application("Composite edit")
    claim = _working_claim(services, app_id, "sales.metric.recurring_customers")

    services.drafts.edit_claim(
        app_id,
        claim.claim_id,
        ["sales.metric.recurring_customers", "sales.metric.performance"],
        template_id="canonical-renderings",
    )

    assert (
        _working_claim(services, app_id, "sales.metric.recurring_customers").claim_type
        == "composite"
    )


def test_render_revalidates_approved_markdown_before_browser(approved_application) -> None:
    setup = approved_application("Acme", "Developer", "Python backend developer API React")
    services, app_id = setup
    markdown_record = services.repository.latest_artifact_version(
        app_id, "resume_markdown", "approved"
    )
    markdown = services.artifacts.resolve(markdown_record["path"])
    markdown.write_text(
        markdown.read_text(encoding="utf-8") + "\nUnsupported claim.\n", encoding="utf-8"
    )
    try:
        services.rendering.render(app_id)
    except WorkflowError as exc:
        assert "approved Markdown" in str(exc)
    else:
        raise AssertionError("modified approved source reached rendering")
