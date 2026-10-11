"""Sign-in for the one user (product-spec §22, state-and-use-cases §23, architecture §18).

Step 2 of the accounts delivery order: the routes and the operator CLI exist, but no
other route requires a session yet.
"""

from __future__ import annotations

import io
import logging
import re

import pytest
from api_harness import MUTATION_HEADERS
from sqlalchemy import insert, select, text, update
from sqlalchemy.exc import IntegrityError

from cv_engine.admin.cli import main as admin
from cv_engine.api.app import API_PREFIX
from cv_engine.api.session_cookie import SESSION_COOKIE
from cv_engine.application.errors import PasswordPolicyFailed, StateConflict
from cv_engine.domain.accounts import (
    EmailRejected,
    PasswordRejected,
    check_password_policy,
    normalize_email,
)
from cv_engine.infrastructure.persistence.tables import user_sessions, users
from cv_engine.util import new_id, sha256_text, utc_now

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


def test_the_database_admits_one_user(services, database_engine) -> None:
    services.accounts.create_user(EMAIL, PASSWORD)

    with pytest.raises(StateConflict, match="second one is refused"):
        services.accounts.create_user("someone.else@example.com", PASSWORD)
    with pytest.raises(StateConflict):
        services.accounts.create_user(EMAIL, PASSWORD)
    # The limit is the index itself, not a check a race could pass.
    with pytest.raises(IntegrityError, match="users_single_user"):
        with database_engine.begin() as connection:
            connection.execute(
                insert(users).values(
                    id=new_id(),
                    email="raw@example.com",
                    password_hash="x",
                    created_at=utc_now(),
                )
            )


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
    token = _token(response)
    assert token not in response.text
    with database_engine.connect() as connection:
        stored = connection.execute(select(user_sessions.c.token_hash)).scalar_one()
    assert stored == sha256_text(token)


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
    assert _post(api_anonymous.client, "logout", first).status_code == 401

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


def test_cli_refuses_a_mismatched_prompt_and_a_second_user(services) -> None:
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
    assert code == 1
    assert "second one is refused" in err.getvalue()


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
