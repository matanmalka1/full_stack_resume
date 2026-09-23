"""Recruitment tracking over HTTP.

What these pin is what the trail is allowed to say. A submission records that
something was sent, and that claim cannot be re-derived afterwards, so the
refusals matter more than the happy path: `applied` cannot be asked for, a
correction cannot be anonymous, and a submission is refused unless the exact
evidence still qualifies.
"""

from __future__ import annotations

from api_harness import MUTATION_HEADERS

from cv_engine.api.app import API_PREFIX
from cv_engine.infrastructure.persistence.application_projections import (
    SqlAlchemyApplicationProjectionReader,
)
from cv_engine.infrastructure.persistence.application_store import SqlAlchemyApplicationStore
from cv_engine.infrastructure.persistence.artifact_catalog import SqlAlchemyArtifactCatalog


def _events(transaction_manager, application_id):
    with transaction_manager.read() as tx:
        return SqlAlchemyApplicationProjectionReader(transaction_manager).recruitment_events(
            tx, application_id
        )


def _application(transaction_manager, application_id):
    with transaction_manager.read() as tx:
        return SqlAlchemyApplicationStore(transaction_manager).get_application(tx, application_id)


def _artifact(transaction_manager, application_id, artifact_type):
    with transaction_manager.read() as tx:
        return SqlAlchemyArtifactCatalog(transaction_manager).latest_artifact_version(
            tx, application_id, artifact_type
        )


def _post(harness, path: str, body: dict | None = None):
    return harness.client.post(f"{API_PREFIX}{path}", json=body or {}, headers=MUTATION_HEADERS)


def _patch(harness, path: str, body: dict):
    return harness.client.patch(f"{API_PREFIX}{path}", json=body, headers=MUTATION_HEADERS)


def _ingested(api_paused, company: str = "Tracking Co") -> str:
    response = _post(
        api_paused,
        "/applications",
        {
            "company": company,
            "target_role": "Account Manager",
            "job_text": "Account Manager responsible for retention and portfolio growth.",
            "acknowledged_duplicates": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["application_id"]


def test_status_transitions_are_recorded_and_repeating_one_is_not_an_error(
    api_paused, transaction_manager
) -> None:
    application_id = _ingested(api_paused)

    moved = _post(
        api_paused,
        f"/applications/{application_id}/status",
        {"target_status": "withdrawn", "reason": "no longer hiring"},
    )
    repeated = _post(
        api_paused,
        f"/applications/{application_id}/status",
        {"target_status": "withdrawn"},
    )

    assert moved.status_code == 200, moved.text
    assert moved.json()["current_status"] == "withdrawn"
    assert moved.json()["event_id"]
    # Asking for the status already held returns the current state rather than
    # appending a second identical event, so a retry cannot duplicate history.
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["current_status"] == "withdrawn"
    events = _events(transaction_manager, application_id)
    assert [event["to_status"] for event in events].count("withdrawn") == 1


def test_applied_cannot_be_asked_for_because_it_is_submission_owned(
    api_paused, transaction_manager
) -> None:
    """state-and-use-cases.md 18: `applied` is reached by recording a submission."""
    application_id = _ingested(api_paused)

    response = _post(
        api_paused,
        f"/applications/{application_id}/status",
        {"target_status": "applied"},
    )

    assert response.status_code == 422, response.text
    assert _application(transaction_manager, application_id)["current_status"] == ("saved")


def test_a_correction_appends_an_event_and_needs_a_reason_and_a_target(
    api_paused, transaction_manager
) -> None:
    """A correction names what should have been recorded, and why.

    `withdrawn` is one of the three statuses reachable from `saved` - the
    interview stages are only reachable once a submission has moved the
    Application to `applied` - so the mis-recorded status here is one an
    Application can actually reach without inventing a submission.
    """
    application_id = _ingested(api_paused)
    moved = _post(
        api_paused,
        f"/applications/{application_id}/status",
        {"target_status": "withdrawn"},
    )
    assert moved.status_code == 200, moved.text
    corrected_event = moved.json()["event_id"]
    before = len(_events(transaction_manager, application_id))

    anonymous = _post(
        api_paused,
        f"/applications/{application_id}/status-corrections",
        {"target_status": "closed", "corrects_event_id": corrected_event},
    )
    corrected = _post(
        api_paused,
        f"/applications/{application_id}/status-corrections",
        {
            "target_status": "closed",
            "corrects_event_id": corrected_event,
            "reason": "recorded against the wrong application",
        },
    )

    assert anonymous.status_code == 422, anonymous.text
    assert corrected.status_code == 201, corrected.text
    assert corrected.json()["current_status"] == "closed"
    events = _events(transaction_manager, application_id)
    # The corrected event is still there: a correction appends, it never edits.
    assert len(events) == before + 1
    assert corrected_event in {event["id"] for event in events}
    timeline = _detail(api_paused, application_id)["recruitment_timeline"]
    projected = {item["id"]: item for item in timeline}
    assert projected[corrected_event]["item_type"] == "status_transition"
    assert projected[corrected.json()["event_id"]]["corrects_event_id"] == corrected_event
    assert projected[corrected.json()["event_id"]]["reason"] == (
        "recorded against the wrong application"
    )


def test_an_internal_submission_records_the_exact_revision_and_pdf(
    api_paused, ready_application, transaction_manager
) -> None:
    setup = ready_application("Submission Co")
    application_id = setup.application_id
    revision_id = setup.approved.revision_id
    pdf = _artifact(transaction_manager, application_id, "resume_pdf")

    response = _post(
        api_paused,
        f"/applications/{application_id}/submissions",
        {
            "approved_revision_id": revision_id,
            "pdf_artifact_version_id": pdf["id"],
            "submitted_at": "2026-08-30T09:00:00+00:00",
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["submission_id"]
    assert body["approved_revision_id"] == revision_id
    assert body["pdf_artifact_version_id"] == pdf["id"]
    # Submission is what moves an Application to `applied`.
    assert body["current_status"] == "applied"
    detail = _detail(api_paused, application_id)
    assert detail["allowed_recruitment_transitions"] == [
        "recruiter_screen",
        "interview",
        "rejected",
        "withdrawn",
        "closed",
    ]
    submitted = next(
        item for item in detail["recruitment_timeline"] if item["id"] == body["submission_id"]
    )
    assert submitted["submission_type"] == "internal"
    assert submitted["approved_revision_id"] == revision_id
    assert submitted["artifact_version_id"] == pdf["id"]


def test_a_submission_naming_the_wrong_pdf_is_refused(
    api_paused, ready_application, transaction_manager
) -> None:
    """The claim that something was sent is not re-derivable, so it must be exact."""
    setup = ready_application("Mismatched PDF Co")
    application_id = setup.application_id
    html = _artifact(transaction_manager, application_id, "resume_html")

    response = _post(
        api_paused,
        f"/applications/{application_id}/submissions",
        {
            "approved_revision_id": setup.approved.revision_id,
            "pdf_artifact_version_id": html["id"],
            "submitted_at": "2026-08-30T09:00:00+00:00",
        },
    )

    assert response.status_code == 412, response.text
    assert _application(transaction_manager, application_id)["current_status"] != ("applied")


def test_an_external_submission_invents_no_revision_or_artifact(api_paused) -> None:
    application_id = _ingested(api_paused, "External Co")

    response = _post(
        api_paused,
        f"/applications/{application_id}/external-submissions",
        {"submitted_at": "2026-08-30T09:00:00+00:00", "metadata": {"note": "sent by email"}},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["current_status"] == "applied"
    # A field that cannot be derived stays null rather than being invented.
    assert body["approved_revision_id"] is None
    assert body["pdf_artifact_version_id"] is None


def test_the_next_action_is_set_and_cleared_as_one_whole_value(api_paused) -> None:
    application_id = _ingested(api_paused, "Next Action Co")

    initial = _detail(api_paused, application_id)
    # `applied` belongs to submission, so the backend-owned direct choices omit it.
    assert initial["allowed_recruitment_transitions"] == ["withdrawn", "closed"]

    set_action = _patch(
        api_paused,
        f"/applications/{application_id}/next-action",
        {"next_action": "follow up with the recruiter", "next_action_date": "2026-09-05"},
    )
    projected_set = _detail(api_paused, application_id)
    cleared = _patch(
        api_paused,
        f"/applications/{application_id}/next-action",
        {"next_action": None, "next_action_date": None},
    )

    assert set_action.status_code == 200, set_action.text
    assert set_action.json()["next_action"] == "follow up with the recruiter"
    assert set_action.json()["next_action_date"] == "2026-09-05"
    assert projected_set["application"]["next_action"] == "follow up with the recruiter"
    assert projected_set["recruitment_timeline"][-1]["next_action"] == (
        "follow up with the recruiter"
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["next_action"] is None
    assert cleared.json()["next_action_date"] is None


def _detail(harness, application_id: str) -> dict:
    response = harness.client.get(f"{API_PREFIX}/applications/{application_id}")
    assert response.status_code == 200, response.text
    return response.json()
