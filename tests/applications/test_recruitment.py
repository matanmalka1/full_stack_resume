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
from cv_engine.infrastructure.persistence.artifact_catalog import SqlAlchemyArtifactCatalog


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


def test_recruitment_http_contract(api_paused) -> None:
    """Status codes and projected history for every tracking mutation.

    The rules themselves are owned by the recruitment service tests in
    test_ready_integrity.py; this pins what HTTP says about them.

    - `applied` cannot be asked for (state-and-use-cases.md 18): it is reached by
      recording a submission, so the backend-owned direct choices omit it.
    - Repeating the status already held returns the current state rather than
      appending a second identical event, so a retry cannot duplicate history.
    - A correction names what should have been recorded, and why, and appends.
      `withdrawn` is reachable from `saved` without inventing a submission.
    - The next action is set and cleared as one whole value, and is not a status.
    - An external submission leaves underivable fields null rather than inventing them.
    """
    application_id = _ingested(api_paused)
    status_path = f"/applications/{application_id}/status"

    initial = _detail(api_paused, application_id)
    assert initial["allowed_recruitment_transitions"] == ["withdrawn", "closed"]
    applied = _post(api_paused, status_path, {"target_status": "applied"})
    assert applied.status_code == 422, applied.text
    assert _detail(api_paused, application_id)["application"]["current_status"] == "saved"

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
    # A next action is not a status: it is its own event and leaves status alone.
    assert set_action.json()["current_status"] == "saved"
    assert projected_set["application"]["current_status"] == "saved"
    assert projected_set["application"]["next_action"] == "follow up with the recruiter"
    assert projected_set["recruitment_timeline"][-1]["item_type"] == "next_action"
    assert projected_set["recruitment_timeline"][-1]["next_action"] == (
        "follow up with the recruiter"
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["next_action"] is None
    assert cleared.json()["next_action_date"] is None

    moved = _post(
        api_paused, status_path, {"target_status": "withdrawn", "reason": "no longer hiring"}
    )
    repeated = _post(api_paused, status_path, {"target_status": "withdrawn"})
    assert moved.status_code == 200, moved.text
    assert moved.json()["current_status"] == "withdrawn"
    assert moved.json()["event_id"]
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["current_status"] == "withdrawn"
    timeline = _detail(api_paused, application_id)["recruitment_timeline"]
    assert [
        item["to_status"] for item in timeline if item["item_type"] == "status_transition"
    ].count("withdrawn") == 1

    corrected_event = moved.json()["event_id"]
    before = len(timeline)
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
    timeline = _detail(api_paused, application_id)["recruitment_timeline"]
    # The corrected event is still there: a correction appends, it never edits.
    assert len(timeline) == before + 1
    projected = {item["id"]: item for item in timeline}
    assert projected[corrected_event]["item_type"] == "status_transition"
    assert projected[corrected.json()["event_id"]]["corrects_event_id"] == corrected_event
    assert projected[corrected.json()["event_id"]]["reason"] == (
        "recorded against the wrong application"
    )

    external_id = _ingested(api_paused, "External Co")
    external = _post(
        api_paused,
        f"/applications/{external_id}/external-submissions",
        {"submitted_at": "2026-08-30T09:00:00+00:00", "metadata": {"note": "sent by email"}},
    )
    assert external.status_code == 201, external.text
    assert external.json()["current_status"] == "applied"
    assert external.json()["approved_revision_id"] is None
    assert external.json()["pdf_artifact_version_id"] is None


def test_an_internal_submission_records_the_exact_revision_and_pdf(
    api_paused, ready_application, transaction_manager
) -> None:
    """The claim that something was sent is not re-derivable, so it must be exact:
    naming the wrong PDF is refused, and the right one moves the Application to
    `applied` with the exact revision and PDF on the timeline."""
    setup = ready_application("Submission Co")
    application_id = setup.application_id
    revision_id = setup.approved.revision_id
    pdf = _artifact(transaction_manager, application_id, "resume_pdf")
    html = _artifact(transaction_manager, application_id, "resume_html")
    submissions_path = f"/applications/{application_id}/submissions"

    mismatched = _post(
        api_paused,
        submissions_path,
        {
            "approved_revision_id": revision_id,
            "pdf_artifact_version_id": html["id"],
            "submitted_at": "2026-08-30T09:00:00+00:00",
        },
    )
    assert mismatched.status_code == 412, mismatched.text
    assert _detail(api_paused, application_id)["application"]["current_status"] != "applied"

    response = _post(
        api_paused,
        submissions_path,
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


def _detail(harness, application_id: str) -> dict:
    response = harness.client.get(f"{API_PREFIX}/applications/{application_id}")
    assert response.status_code == 200, response.text
    return response.json()
