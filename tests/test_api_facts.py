"""The fact lifecycle over HTTP.

What these pin is the specification's refusals, not just the happy path: a
promotion without explicit confirmation must fail, identity must not be
caller-chosen, and only a canonical fact may enter a Profile pool. Each of
those previously lacked an API surface.
"""

from __future__ import annotations

from api_harness import MUTATION_HEADERS

from cv_engine.api.app import API_PREFIX


def _content(**overrides) -> dict:
    return {
        "source": "situational_skills.md",
        "meaning": "candidate has production PostgreSQL experience",
        "renderings": {"en": "PostgreSQL"},
        "tags": ["database"],
        "provenance": "stated by the candidate",
        "resume_style": "item",
        **overrides,
    }


def _post(harness, path: str, body: dict):
    return harness.client.post(f"{API_PREFIX}{path}", json=body, headers=MUTATION_HEADERS)


def _create_pending(harness, **overrides) -> dict:
    response = _post(harness, "/facts", _content(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def test_fact_http_journey_creates_reads_promotes_and_lists(api_worker) -> None:
    """One journey proves that the related success contracts compose over HTTP."""
    created = _create_pending(api_worker)
    fact_id = created["fact"]["fact_id"]

    assert created["fact"]["status"] == "pending"
    assert created["fact"]["meaning"] == "candidate has production PostgreSQL experience"
    assert created["event_id"]
    # Identity is generated, never supplied: a pending fact carries an opaque
    # ID rather than anything the caller could have chosen.
    assert fact_id
    assert fact_id != "postgres"

    confirmed = _post(api_worker, f"/facts/{fact_id}/confirm", {"confirm": True})
    promoted = _post(api_worker, f"/facts/{fact_id}/promote", {"confirm": True})

    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["fact"]["status"] == "confirmed"
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["fact"]["status"] == "canonical"

    detail = api_worker.client.get(f"{API_PREFIX}/facts/{fact_id}")
    listed = api_worker.client.get(f"{API_PREFIX}/facts", params={"status": "canonical"})
    history = api_worker.client.get(f"{API_PREFIX}/facts/{fact_id}/history")

    assert detail.status_code == 200, detail.text
    assert detail.json()["fact"]["fact_id"] == fact_id
    assert detail.json()["events"], "a created fact has at least its creation event"
    assert listed.status_code == 200, listed.text
    assert fact_id in {item["fact"]["fact_id"] for item in listed.json()["items"]}
    assert history.status_code == 200, history.text
    transitions = [(event["from_status"], event["to_status"]) for event in history.json()["events"]]
    # Each transition is recorded separately, so the trail shows the path taken
    # rather than only where the fact ended up.
    assert (None, "pending") in transitions
    assert ("pending", "confirmed") in transitions
    assert ("confirmed", "canonical") in transitions


def test_fact_http_refusals_preserve_the_pending_fact(api_worker) -> None:
    """Transport and lifecycle refusals share one unchanged source fact."""
    # product-spec.md 561: the UI does not expose fact-ID creation.
    chosen_identity = _post(
        api_worker,
        "/facts",
        _content(fact_id="situational.postgres"),
    )
    assert chosen_identity.status_code == 422, chosen_identity.text

    created = _create_pending(api_worker)
    fact_id = created["fact"]["fact_id"]

    refusals = [
        (_post(api_worker, f"/facts/{fact_id}/confirm", {}), 412),
        (
            _post(
                api_worker,
                f"/facts/{fact_id}/attachments",
                {"profile": "tech-sales", "section": "Professional Summary"},
            ),
            412,
        ),
        (api_worker.client.get(f"{API_PREFIX}/facts/does-not-exist"), 404),
    ]
    for response, expected_status in refusals:
        assert response.status_code == expected_status, response.text
    assert api_worker.services.knowledge_lifecycle.show_fact(fact_id).fact.status.value == "pending"
