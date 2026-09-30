from __future__ import annotations

import pytest
from api_harness import MUTATION_HEADERS

from cv_engine.api.app import API_PREFIX

SETTINGS_FIELDS = {
    "edit_version",
    "auto_generate_when_review_not_required",
    "default_ai_model",
    "default_reasoning_effort",
    "available_ai_models",
    "ui_density",
    "ui_text_size",
    "ui_theme",
    "provider_configured",
    "updated_at",
}


def _update_body(**overrides) -> dict:
    return {
        "auto_generate_when_review_not_required": False,
        "default_ai_model": "gpt-5.6-terra",
        "default_reasoning_effort": "medium",
        "ui_density": "comfortable",
        "ui_text_size": "normal",
        "ui_theme": "system",
        **overrides,
    }


def _patch(harness, etag: str, body: dict):
    return harness.client.patch(
        f"{API_PREFIX}/settings",
        json=body,
        headers={**MUTATION_HEADERS, "If-Match": etag},
    )


def test_settings_api_returns_pure_defaults_etag_and_no_secret_surface(api_worker) -> None:
    response = api_worker.client.get(f"{API_PREFIX}/settings")

    assert response.status_code == 200, response.text
    assert response.headers["ETag"] == '"settings-0"'
    assert response.json() == {
        "edit_version": 0,
        "auto_generate_when_review_not_required": False,
        # The catalog's `recommended` model. This assertion used to read
        # `gpt-5.6-sol` - it pinned the defect rather than the contract, because
        # the `CV_MODEL` default was the `gpt-5.6` family alias and resolving it
        # picked the most expensive tier.
        "default_ai_model": "gpt-5.6-terra",
        "default_reasoning_effort": "medium",
        "available_ai_models": [
            {
                "id": "gpt-5.6-luna",
                "label": "GPT-5.6 Luna",
                "input_per_million_usd": "0.20",
                "cached_input_per_million_usd": "0.02",
                "output_per_million_usd": "1.20",
                "recommended": False,
                "pricing_version": "openai-2026-09-03",
                "pricing_source": "https://developers.openai.com/api/docs/models/compare",
            },
            {
                "id": "gpt-5.6-terra",
                "label": "GPT-5.6 Terra",
                "input_per_million_usd": "2.00",
                "cached_input_per_million_usd": "0.20",
                "output_per_million_usd": "12.00",
                "recommended": True,
                "pricing_version": "openai-2026-09-03",
                "pricing_source": "https://developers.openai.com/api/docs/models/compare",
            },
            {
                "id": "gpt-5.6-sol",
                "label": "GPT-5.6 Sol",
                "input_per_million_usd": "4.00",
                "cached_input_per_million_usd": "0.40",
                "output_per_million_usd": "20.00",
                "recommended": False,
                "pricing_version": "openai-2026-09-03",
                "pricing_source": "https://developers.openai.com/api/docs/models/compare",
            },
        ],
        "ui_density": "comfortable",
        "ui_text_size": "normal",
        "ui_theme": "system",
        "provider_configured": False,
        "updated_at": None,
    }
    assert set(response.json()) == SETTINGS_FIELDS
    assert not any(
        token in key.casefold()
        for key in response.json()
        for token in ("key", "secret", "token", "credential")
    )


@pytest.mark.parametrize(
    ("harness_fixture", "configured"),
    [("ai_api_worker", True), ("api_worker", False)],
    ids=["provider-configured", "provider-unconfigured"],
)
def test_ai_availability_is_the_provider_configuration(
    request, harness_fixture, configured
) -> None:
    """AI has no switch of its own: it is available exactly when a provider is configured."""
    response = request.getfixturevalue(harness_fixture).client.get(f"{API_PREFIX}/settings")
    assert response.status_code == 200, response.text
    assert response.json()["provider_configured"] is configured


def test_settings_patch_updates_live_and_rejects_a_stale_etag_without_writing(
    api_worker,
) -> None:
    initial = api_worker.client.get(f"{API_PREFIX}/settings")
    requested = _update_body(
        auto_generate_when_review_not_required=True,
        ui_density="compact",
        ui_text_size="large",
        default_ai_model="gpt-5.6-luna",
        default_reasoning_effort="low",
        ui_theme="dark",
    )

    updated = _patch(api_worker, initial.headers["ETag"], requested)
    assert updated.status_code == 200, updated.text
    assert updated.headers["ETag"] == '"settings-1"'
    assert updated.json()["edit_version"] == 1
    assert {key: updated.json()[key] for key in requested} == requested
    assert api_worker.client.get(f"{API_PREFIX}/settings").json() == updated.json()

    stale = _patch(api_worker, initial.headers["ETag"], _update_body())
    assert stale.status_code == 409, stale.text
    assert stale.json()["code"] == "STATE_CONFLICT"
    after = api_worker.client.get(f"{API_PREFIX}/settings")
    assert after.headers["ETag"] == updated.headers["ETag"]
    assert after.json() == updated.json()


def test_settings_round_trip_every_theme_and_reject_values_outside_their_catalogs(
    api_worker,
) -> None:
    initial = api_worker.client.get(f"{API_PREFIX}/settings")
    for body in (
        _update_body(default_ai_model="provider-model-not-in-catalog"),
        _update_body(default_reasoning_effort="maximum"),
    ):
        refused = _patch(api_worker, initial.headers["ETag"], body)
        assert refused.status_code == 422, refused.text
    unchanged = api_worker.client.get(f"{API_PREFIX}/settings")
    assert unchanged.headers["ETag"] == initial.headers["ETag"]

    etag = initial.headers["ETag"]
    for theme in ("system", "light", "dark"):
        saved = _patch(api_worker, etag, _update_body(ui_theme=theme))
        assert saved.status_code == 200
        assert saved.json()["ui_theme"] == theme
        assert api_worker.client.get(f"{API_PREFIX}/settings").json()["ui_theme"] == theme
        refused = _patch(api_worker, saved.headers["ETag"], _update_body(ui_theme="sepia"))
        assert refused.status_code == 422
        assert api_worker.client.get(f"{API_PREFIX}/settings").json() == saved.json()
        etag = saved.headers["ETag"]
