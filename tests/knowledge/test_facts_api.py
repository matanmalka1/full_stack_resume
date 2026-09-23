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
        "source": "situational_skills.json",
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


def test_fact_attachment_targets_are_read_only_and_report_existing_membership(api_worker) -> None:
    before = api_worker.client.get(f"{API_PREFIX}/facts/attachment-targets")
    assert before.status_code == 200, before.text
    profiles = before.json()["profiles"]
    assert profiles
    target_profile = next(item for item in profiles if item["profile"] == "tech-sales")
    target_section = target_profile["sections"][0]
    assert {"section", "label", "attached", "pinned"} <= target_section.keys()
    assert target_section["attached"] is False

    created = _create_pending(api_worker)
    fact_id = created["fact"]["fact_id"]
    _post(api_worker, f"/facts/{fact_id}/confirm", {"confirm": True})
    _post(api_worker, f"/facts/{fact_id}/promote", {"confirm": True})
    attached = _post(
        api_worker,
        f"/facts/{fact_id}/attachments",
        {
            "profile": target_profile["profile"],
            "section": target_section["section"],
            "pin": True,
        },
    )
    assert attached.status_code == 201, attached.text

    after = api_worker.client.get(
        f"{API_PREFIX}/facts/attachment-targets", params={"fact_id": fact_id}
    )
    assert after.status_code == 200, after.text
    profile = next(item for item in after.json()["profiles"] if item["profile"] == "tech-sales")
    section = next(
        item for item in profile["sections"] if item["section"] == target_section["section"]
    )
    assert section["attached"] is True
    assert section["pinned"] is True

    missing = api_worker.client.get(
        f"{API_PREFIX}/facts/attachment-targets", params={"fact_id": "does-not-exist"}
    )
    assert missing.status_code == 404, missing.text


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
    assert api_worker.services.knowledge_queries.show_fact(fact_id).fact.status.value == "pending"
