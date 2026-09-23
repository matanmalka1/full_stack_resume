from __future__ import annotations

from helpers import ACCOUNT_MANAGER_JOB, validate_active_draft
from helpers import working_claim as _working_claim

from cv_engine.domain.draft_markdown import parse_draft, serialize_markdown
from cv_engine.infrastructure.artifacts import FilesystemArtifactStore
from cv_engine.runtime.paths import AppPaths


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
        profile_override="development",
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
