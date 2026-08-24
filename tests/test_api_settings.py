from __future__ import annotations

from api_harness import MUTATION_HEADERS

from cv_engine.api.app import API_PREFIX


SETTINGS_FIELDS = {
    "edit_version",
    "auto_generate_when_review_not_required",
    "ai_enabled",
    "ai_enabled_override",
    "default_execution_mode",
    "open_browser_on_launch",
    "ui_density",
    "ui_text_size",
    "provider_configured",
    "updated_at",
}


def _update_body(**overrides) -> dict:
    return {
        "auto_generate_when_review_not_required": False,
        "ai_enabled_override": None,
        "default_execution_mode": "deterministic",
        "open_browser_on_launch": True,
        "ui_density": "comfortable",
        "ui_text_size": "normal",
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
        "ai_enabled": False,
        "ai_enabled_override": None,
        "default_execution_mode": "deterministic",
        "open_browser_on_launch": True,
        "ui_density": "comfortable",
        "ui_text_size": "normal",
        "provider_configured": False,
        "updated_at": None,
    }
    assert set(response.json()) == SETTINGS_FIELDS
    assert not any(
        token in key.casefold()
        for key in response.json()
        for token in ("key", "secret", "token", "credential")
    )


def test_ai_enabled_is_derived_from_provider_until_an_override_is_stored(
    ai_api_worker,
) -> None:
    initial = ai_api_worker.client.get(f"{API_PREFIX}/settings")
    assert initial.status_code == 200, initial.text
    assert initial.json()["provider_configured"] is True
    assert initial.json()["ai_enabled"] is True
    assert initial.json()["ai_enabled_override"] is None

    disabled = _patch(
        ai_api_worker,
        initial.headers["ETag"],
        _update_body(ai_enabled_override=False),
    )
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["provider_configured"] is True
    assert disabled.json()["ai_enabled_override"] is False
    assert disabled.json()["ai_enabled"] is False


def test_stored_true_override_does_not_report_ai_enabled_without_a_provider(
    api_worker,
) -> None:
    initial = api_worker.client.get(f"{API_PREFIX}/settings")
    stored = _patch(
        api_worker,
        initial.headers["ETag"],
        _update_body(ai_enabled_override=True),
    )

    assert stored.status_code == 200, stored.text
    assert stored.json()["provider_configured"] is False
    assert stored.json()["ai_enabled_override"] is True
    assert stored.json()["ai_enabled"] is False


def test_settings_patch_updates_live_and_rejects_a_stale_etag_without_writing(
    api_worker,
) -> None:
    initial = api_worker.client.get(f"{API_PREFIX}/settings")
    requested = _update_body(
        auto_generate_when_review_not_required=True,
        ai_enabled_override=False,
        open_browser_on_launch=False,
        ui_density="compact",
        ui_text_size="large",
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


def test_ai_default_mode_requires_a_configured_provider(api_worker) -> None:
    unconfigured = api_worker.client.get(f"{API_PREFIX}/settings")
    refused_unconfigured = _patch(
        api_worker,
        unconfigured.headers["ETag"],
        _update_body(ai_enabled_override=True, default_execution_mode="ai"),
    )
    assert refused_unconfigured.status_code == 412, refused_unconfigured.text
    assert refused_unconfigured.json()["code"] == "PRECONDITION_FAILED"


def test_ai_default_mode_requires_effective_ai_to_remain_enabled(ai_api_worker) -> None:
    configured = ai_api_worker.client.get(f"{API_PREFIX}/settings")
    refused_disabled = _patch(
        ai_api_worker,
        configured.headers["ETag"],
        _update_body(ai_enabled_override=False, default_execution_mode="ai"),
    )
    assert refused_disabled.status_code == 412, refused_disabled.text
    assert refused_disabled.json()["code"] == "PRECONDITION_FAILED"
    assert ai_api_worker.client.get(f"{API_PREFIX}/settings").headers["ETag"] == configured.headers[
        "ETag"
    ]
