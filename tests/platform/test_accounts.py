"""Accounts, sessions, and the shared sign-in throttle."""

from __future__ import annotations

import io
import logging
import re
from datetime import UTC, datetime, timedelta

import pytest
from api_harness import MUTATION_HEADERS
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import select, text, update
from starlette.requests import Request

from cv_engine.admin.cli import main as admin
from cv_engine.api.app import API_PREFIX, create_app
from cv_engine.api.client_address import client_ip
from cv_engine.api.session_cookie import SESSION_COOKIE
from cv_engine.application.errors import PasswordPolicyFailed, RateLimited, StateConflict
from cv_engine.domain.accounts import (
    EmailRejected,
    PasswordRejected,
    check_password_policy,
    normalize_email,
)
from cv_engine.infrastructure.persistence.tables import rate_limit_buckets, user_sessions, users
from cv_engine.runtime.composition import build_api_services, build_services
from cv_engine.util import sha256_text

EMAIL = "Candidate@Example.com"
PASSWORD = "correct horse battery"
OTHER_PASSWORD = "another long password"


def _login(client, email: str = EMAIL, password: str = PASSWORD):
    return client.post(
        f"{API_PREFIX}/auth/login",
        json={"email": email, "password": password},
        headers=MUTATION_HEADERS,
    )


def _token(response) -> str:
    # The cookie is `Secure`, so the test client's jar keeps it off plain-HTTP
    # requests; tests carry it explicitly, as a browser on https would.
    return response.cookies[SESSION_COOKIE]


def _session(token: str) -> dict[str, str]:
    return {"Cookie": f"{SESSION_COOKIE}={token}"}


def _post(client, path: str, token: str, body: dict | None = None):
    return client.post(
        f"{API_PREFIX}/auth/{path}",
        json=body,
        headers={**MUTATION_HEADERS, **_session(token)},
    )


def _me(client, token: str):
    return client.get(f"{API_PREFIX}/auth/me", headers=_session(token))


@pytest.fixture
def services(bare_services):
    """These tests make the user themselves: services with no user and no Knowledge."""
    return bare_services


@pytest.mark.parametrize(
    ("raw", "stored"),
    [
        (" Candidate@Example.COM ", "candidate@example.com"),
        ("é@example.com", "é@example.com"),
    ],
)
def test_email_is_stored_nfc_trimmed_and_lowercased(raw: str, stored: str) -> None:
    assert normalize_email(raw) == stored


@pytest.mark.parametrize("raw", ["", "no-at-sign", "@example.com", "a@", "a@b@c", "a b@c.d"])
def test_text_that_cannot_be_an_address_is_refused(raw: str) -> None:
    with pytest.raises(EmailRejected):
        normalize_email(raw)


def test_password_policy_is_length_only() -> None:
    check_password_policy("a" * 12)
    check_password_policy("a" * 256)
    for refused in ("a" * 11, "a" * 257):
        with pytest.raises(PasswordRejected):
            check_password_policy(refused)


def test_create_user_stores_a_normalized_email_and_only_an_argon2_hash(
    services, database_engine
) -> None:
    user = services.accounts.create_user(EMAIL, PASSWORD)

    assert user.email == "candidate@example.com"
    with database_engine.connect() as connection:
        row = connection.execute(select(users)).mappings().one()
    assert row["email"] == "candidate@example.com"
    assert row["password_hash"].startswith("$argon2id$")
    assert PASSWORD not in row["password_hash"]


def test_the_database_admits_multiple_users_but_keeps_email_unique(
    services, database_engine
) -> None:
    first = services.accounts.create_user(EMAIL, PASSWORD)
    second = services.accounts.create_user("someone.else@example.com", PASSWORD)

    assert first.id != second.id
    with pytest.raises(StateConflict):
        services.accounts.create_user(EMAIL, PASSWORD)
    with database_engine.connect() as connection:
        assert {str(value) for value in connection.execute(select(users.c.id)).scalars()} == {
            first.id,
            second.id,
        }


def test_create_user_refuses_a_password_outside_the_policy(services) -> None:
    with pytest.raises(PasswordPolicyFailed):
        services.accounts.create_user(EMAIL, "short")


def test_login_sets_a_host_only_secure_http_only_lax_cookie_and_stores_only_its_hash(
    api_anonymous, database_engine
) -> None:
    api_anonymous.services.accounts.create_user(EMAIL, PASSWORD)

    response = _login(api_anonymous.client)

    assert response.status_code == 200, response.text
    assert response.json() == {
        "id": response.json()["id"],
        "email": "candidate@example.com",
        "created_at": response.json()["created_at"],
    }
    cookie = response.headers["set-cookie"]
    attributes = {part.strip().split("=")[0].lower() for part in cookie.split(";")}
    assert cookie.startswith(f"{SESSION_COOKIE}=")
    assert {"httponly", "secure", "path", "expires"} <= attributes
    assert "samesite=lax" in cookie.lower()
    assert "domain" not in attributes
    assert response.headers["cache-control"] == "no-store"
    token = _token(response)
    assert token not in response.text
    with database_engine.connect() as connection:
        stored = connection.execute(select(user_sessions.c.token_hash)).scalar_one()
    assert stored == sha256_text(token)


def test_signing_in_again_ends_the_session_the_browser_presented(api_anonymous) -> None:
    api_anonymous.services.accounts.create_user(EMAIL, PASSWORD)
    first = _token(_login(api_anonymous.client))

    again = api_anonymous.client.post(
        f"{API_PREFIX}/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
        headers={**MUTATION_HEADERS, **_session(first)},
    )

    assert again.status_code == 200
    assert _me(api_anonymous.client, first).status_code == 401
    assert _me(api_anonymous.client, _token(again)).status_code == 200


def test_a_hash_from_weaker_parameters_is_replaced_at_sign_in(
    api_anonymous, database_engine
) -> None:
    user = api_anonymous.services.accounts.create_user(EMAIL, PASSWORD)
    weak = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash(PASSWORD)
    with database_engine.begin() as connection:
        connection.execute(update(users).values(password_hash=weak))

    assert _login(api_anonymous.client).status_code == 200

    with database_engine.connect() as connection:
        stored = connection.execute(
            select(users.c.password_hash).where(users.c.id == user.id)
        ).scalar_one()
    assert stored != weak
    assert not PasswordHasher().check_needs_rehash(stored)
    assert _login(api_anonymous.client).status_code == 200


def test_unknown_email_and_wrong_password_get_the_same_answer_and_log_no_credentials(
    api_anonymous, caplog
) -> None:
    api_anonymous.services.accounts.create_user(EMAIL, PASSWORD)
    caplog.set_level(logging.DEBUG)

    wrong_password = _login(api_anonymous.client, password="not the password")
    unknown_email = _login(api_anonymous.client, email="nobody@example.com")
    not_an_email = _login(api_anonymous.client, email="nobody")

    for response in (wrong_password, unknown_email, not_an_email):
        assert response.status_code == 401
        assert response.json()["code"] == "INVALID_CREDENTIALS"
        assert SESSION_COOKIE not in response.headers.get("set-cookie", "")
    assert wrong_password.json() == unknown_email.json() == not_an_email.json()
    assert "sign-in failed" in caplog.text
    for secret in ("not the password", PASSWORD, "nobody@example.com", "candidate@"):
        assert secret not in caplog.text


def test_login_needs_an_allowed_origin(api_anonymous) -> None:
    api_anonymous.services.accounts.create_user(EMAIL, PASSWORD)

    response = api_anonymous.client.post(
        f"{API_PREFIX}/auth/login", json={"email": EMAIL, "password": PASSWORD}
    )

    assert response.status_code == 403
    assert response.json()["code"] == "ORIGIN_NOT_ALLOWED"


def test_me_requires_a_valid_session(api_anonymous, database_engine) -> None:
    api_anonymous.services.accounts.create_user(EMAIL, PASSWORD)
    token = _token(_login(api_anonymous.client))

    assert _me(api_anonymous.client, token).json()["email"] == "candidate@example.com"
    for headers in ({}, _session("not-a-session")):
        response = api_anonymous.client.get(f"{API_PREFIX}/auth/me", headers=headers)
        assert response.status_code == 401
        assert response.json()["code"] == "AUTHENTICATION_REQUIRED"

    with database_engine.begin() as connection:
        connection.execute(
            update(user_sessions).values(expires_at=text("now() - interval '1 second'"))
        )
    assert _me(api_anonymous.client, token).status_code == 401


def test_logout_ends_this_session_and_logout_all_ends_every_one(api_anonymous) -> None:
    api_anonymous.services.accounts.create_user(EMAIL, PASSWORD)
    first = _token(_login(api_anonymous.client))
    second = _token(_login(api_anonymous.client))
    assert first != second

    response = _post(api_anonymous.client, "logout", first)
    assert response.status_code == 204
    assert f"{SESSION_COOKIE}=" in response.headers["set-cookie"]
    assert _me(api_anonymous.client, first).status_code == 401
    assert _me(api_anonymous.client, second).status_code == 200
    # Signing out of a session that already ended still answers 204 and clears the
    # cookie: the reader asked to leave, and a stale cookie must not stay behind.
    for headers in (_session(first), {}):
        stale = api_anonymous.client.post(
            f"{API_PREFIX}/auth/logout", headers={**MUTATION_HEADERS, **headers}
        )
        assert stale.status_code == 204
        assert f"{SESSION_COOKIE}=" in stale.headers["set-cookie"]
        assert stale.headers["cache-control"] == "no-store"

    third = _token(_login(api_anonymous.client))
    assert _post(api_anonymous.client, "logout-all", third).status_code == 204
    assert _me(api_anonymous.client, second).status_code == 401
    assert _me(api_anonymous.client, third).status_code == 401


def test_change_password_needs_the_current_one_and_rotates_every_session(api_anonymous) -> None:
    api_anonymous.services.accounts.create_user(EMAIL, PASSWORD)
    current = _token(_login(api_anonymous.client))
    other = _token(_login(api_anonymous.client))

    wrong = _post(
        api_anonymous.client,
        "change-password",
        current,
        {"current_password": "not the password", "new_password": OTHER_PASSWORD},
    )
    assert wrong.status_code == 401
    assert wrong.json()["code"] == "REAUTHENTICATION_FAILED"
    short = _post(
        api_anonymous.client,
        "change-password",
        current,
        {"current_password": PASSWORD, "new_password": "short"},
    )
    assert short.status_code == 422
    assert short.json()["code"] == "PASSWORD_POLICY_FAILED"
    assert _me(api_anonymous.client, other).status_code == 200

    changed = _post(
        api_anonymous.client,
        "change-password",
        current,
        {"current_password": PASSWORD, "new_password": OTHER_PASSWORD},
    )

    assert changed.status_code == 204
    rotated = _token(changed)
    assert _me(api_anonymous.client, rotated).status_code == 200
    assert _me(api_anonymous.client, current).status_code == 401
    assert _me(api_anonymous.client, other).status_code == 401
    assert _login(api_anonymous.client).status_code == 401
    assert _login(api_anonymous.client, password=OTHER_PASSWORD).status_code == 200


def test_cli_creates_the_user_from_stdin_or_a_twice_entered_prompt(services, api_anonymous) -> None:
    out, err = io.StringIO(), io.StringIO()
    code = admin(
        ["create-user", "--email", EMAIL, "--password-stdin"],
        services=services,
        stdin=io.StringIO(PASSWORD + "\n"),
        out=out,
        err=err,
    )
    assert code == 0, err.getvalue()
    assert "candidate@example.com" in out.getvalue()
    assert PASSWORD not in out.getvalue() + err.getvalue()
    assert _login(api_anonymous.client).status_code == 200

    answers = iter([OTHER_PASSWORD, OTHER_PASSWORD])
    code = admin(
        ["set-password", "--email", EMAIL],
        services=services,
        prompt=lambda _label: next(answers),
        out=io.StringIO(),
        err=io.StringIO(),
    )
    assert code == 0
    assert _login(api_anonymous.client, password=OTHER_PASSWORD).status_code == 200


def test_cli_refuses_a_mismatched_prompt_and_creates_a_second_user(services) -> None:
    answers = iter([PASSWORD, "something else entirely"])
    err = io.StringIO()
    code = admin(
        ["create-user", "--email", EMAIL],
        services=services,
        prompt=lambda _label: next(answers),
        out=io.StringIO(),
        err=err,
    )
    assert code == 1
    assert "do not match" in err.getvalue()

    services.accounts.create_user(EMAIL, PASSWORD)
    err = io.StringIO()
    code = admin(
        ["create-user", "--email", "second@example.com", "--password-stdin"],
        services=services,
        stdin=io.StringIO(PASSWORD),
        out=io.StringIO(),
        err=err,
    )
    assert code == 0, err.getvalue()


def test_sign_in_rate_limit_is_shared_and_returns_retry_after(
    api_anonymous, database_engine
) -> None:
    now = [datetime(2026, 10, 11, 12, 1, tzinfo=UTC)]
    api_anonymous.services.accounts.clock = lambda: now[0]
    api_anonymous.services.accounts.create_user(EMAIL, PASSWORD)

    # A successful sign-in gives back the count its reservation took: it is not a failure.
    assert _login(api_anonymous.client, password=PASSWORD).status_code == 200
    for _ in range(5):
        response = _login(api_anonymous.client, password="wrong password")
        assert response.status_code == 401

    limited = _login(api_anonymous.client, password=PASSWORD)
    assert limited.status_code == 429
    assert limited.json()["code"] == "RATE_LIMITED"
    assert 1 <= int(limited.headers["Retry-After"]) <= 15 * 60

    with database_engine.connect() as connection:
        rows = connection.execute(select(rate_limit_buckets)).mappings().all()
    assert {row["bucket_type"] for row in rows} == {"email_failure", "client_attempt"}
    assert all(len(row["key_hash"]) == 64 for row in rows)
    assert EMAIL.lower() not in repr(rows)
    assert "testclient" not in repr(rows)

    now[0] += timedelta(minutes=15)
    assert _login(api_anonymous.client, password=PASSWORD).status_code == 200


def test_attempts_in_flight_are_counted_when_they_start(api_anonymous) -> None:
    """Each attempt is counted by the statement that reserves it, before its outcome is
    known, so attempts racing each other cannot all see room under the email limit."""
    accounts = api_anonymous.services.accounts
    now = datetime(2026, 10, 11, 12, 1, tzinfo=UTC)
    key = accounts._email_rate_key(EMAIL)
    for index in range(5):
        accounts._reserve_attempt(key, sha256_text(f"client:{index}"), now)
    with pytest.raises(RateLimited):
        accounts._reserve_attempt(key, sha256_text("client:late"), now)


def test_sign_in_rate_limit_is_shared_by_independent_api_compositions(api_anonymous) -> None:
    api_anonymous.services.accounts.create_user(EMAIL, PASSWORD)
    second_services = build_services(
        api_anonymous.services.paths,
        database_url=api_anonymous.services.database_url,
    )
    with TestClient(create_app(build_api_services(second_services))) as second_client:
        for _ in range(3):
            assert _login(api_anonymous.client, password="wrong password").status_code == 401
        for _ in range(2):
            assert _login(second_client, password="wrong password").status_code == 401
        limited = _login(second_client, password=PASSWORD)
    assert limited.status_code == 429
    assert limited.json()["code"] == "RATE_LIMITED"


def test_rate_limit_cleanup_removes_only_completed_windows(api_anonymous, database_engine) -> None:
    api_anonymous.services.accounts.create_user(EMAIL, PASSWORD)
    assert _login(api_anonymous.client, password="wrong password").status_code == 401
    with database_engine.begin() as connection:
        connection.execute(
            update(rate_limit_buckets).values(
                window_started_at=(datetime.now(UTC) - timedelta(hours=1)).isoformat()
            )
        )
    assert api_anonymous.services.accounts.cleanup_rate_limits() == 2
    with database_engine.connect() as connection:
        assert connection.execute(select(rate_limit_buckets)).all() == []


def test_client_address_trusts_forwarding_only_for_configured_proxy_hops() -> None:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [(b"x-forwarded-for", b"198.51.100.10, 192.0.2.4")],
            "client": ("203.0.113.8", 443),
        }
    )
    assert client_ip(request, 0) == "203.0.113.8"
    assert client_ip(request, 1) == "192.0.2.4"
    assert client_ip(request, 2) == "198.51.100.10"

    invalid = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [(b"x-forwarded-for", b"attacker-controlled-text")],
            "client": ("203.0.113.8", 443),
        }
    )
    assert client_ip(invalid, 1) == "203.0.113.8"


def test_client_attempt_limit_spans_email_addresses(api_anonymous) -> None:
    api_anonymous.services.accounts.create_user(EMAIL, PASSWORD)

    for index in range(20):
        response = _login(api_anonymous.client, email=f"unknown-{index}@example.com")
        assert response.status_code == 401

    limited = _login(api_anonymous.client)
    assert limited.status_code == 429
    assert limited.json()["code"] == "RATE_LIMITED"


def test_set_password_ends_every_session(api_anonymous) -> None:
    api_anonymous.services.accounts.create_user(EMAIL, PASSWORD)
    token = _token(_login(api_anonymous.client))

    api_anonymous.services.accounts.set_password(EMAIL, OTHER_PASSWORD)

    assert _me(api_anonymous.client, token).status_code == 401
    assert _login(api_anonymous.client, password=OTHER_PASSWORD).status_code == 200


# Routes that answer without a session. Everything else in the schema must refuse.
# A stale entry fails too, so the list cannot outlive the route it excuses.
SESSIONLESS_ROUTES = frozenset(
    {
        ("get", "/api/v1/health"),
        ("post", "/api/v1/auth/login"),
        # The rest of `/auth` resolves its own session and answers 401 by itself.
        ("post", "/api/v1/auth/logout"),
        ("post", "/api/v1/auth/logout-all"),
        ("get", "/api/v1/auth/me"),
        ("post", "/api/v1/auth/change-password"),
    }
)


def test_every_route_in_the_schema_requires_a_session_unless_excepted(api_anonymous) -> None:
    """Derived from the published schema, not a hand list of what to protect."""
    client = api_anonymous.client
    schema = client.get(f"{API_PREFIX}/openapi.json").json()
    routes = {
        (method, path)
        for path, operations in schema["paths"].items()
        for method in operations
        if method in {"get", "post", "patch", "put", "delete"}
    }
    assert SESSIONLESS_ROUTES <= routes, sorted(SESSIONLESS_ROUTES - routes)

    open_routes = []
    for method, path in sorted(routes - SESSIONLESS_ROUTES):
        concrete = re.sub(r"\{[^}]+\}", "00000000-0000-4000-8000-000000000000", path)
        response = client.request(method.upper(), concrete, headers=MUTATION_HEADERS)
        if response.status_code != 401 or response.json()["code"] != "AUTHENTICATION_REQUIRED":
            open_routes.append((method, path, response.status_code))
    assert not open_routes, open_routes
