"""Derived proof that every record-addressed HTTP route is owner-scoped."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from api_harness import ALLOWED_ORIGIN, MUTATION_HEADERS
from fastapi.testclient import TestClient
from helpers import actor_of, persisted_counts, services_transactions
from sqlalchemy import func, select

from cv_engine.api.app import API_PREFIX, create_app
from cv_engine.api.session_cookie import SESSION_COOKIE
from cv_engine.application.actor import Actor
from cv_engine.application.commands import AnalyzeCommand, IngestCommand
from cv_engine.application.settings import UpdateSettings
from cv_engine.infrastructure.knowledge import FileKnowledge
from cv_engine.infrastructure.persistence.tables import facts
from cv_engine.runtime.composition import build_api_services
from cv_engine.util import new_id, utc_now

OTHER_EMAIL = "other@example.com"
OTHER_PASSWORD = "another password, long enough"


@dataclass(frozen=True)
class ForeignRequest:
    method: str
    path: str
    json: dict[str, object] | None = None
    headers: dict[str, str] | None = None


def _record_routes(schema: dict[str, object]) -> set[tuple[str, str]]:
    paths = cast(dict[str, dict[str, object]], schema["paths"])
    components = cast(dict[str, dict[str, dict[str, object]]], schema["components"])["schemas"]
    # Derived, not listed: any path parameter or body property naming an ID addresses a
    # record, so a route that gains a new kind of ID joins this matrix without anyone
    # remembering to add it.
    routes: set[tuple[str, str]] = set()
    for path, operations in paths.items():
        for method, raw_operation in operations.items():
            if method not in {"get", "post", "patch", "delete"}:
                continue
            operation = cast(dict[str, object], raw_operation)
            parameters = cast(list[dict[str, object]], operation.get("parameters", []))
            parameter_names = {str(parameter.get("name")) for parameter in parameters}
            request_body = cast(dict[str, object], operation.get("requestBody", {}))
            content = cast(dict[str, dict[str, object]], request_body.get("content", {}))
            body_schema = cast(
                dict[str, str], content.get("application/json", {}).get("schema", {})
            )
            body_ref = body_schema.get("$ref", "").rsplit("/", 1)[-1]
            body_properties = set(
                cast(dict[str, object], components.get(body_ref, {})).get("properties", {})
            )
            if any(name.endswith("_id") for name in parameter_names | body_properties):
                routes.add((method.upper(), path))
    return routes


def test_every_record_route_hides_foreign_records_and_writes_nothing(
    submitted_application, project_root, database_engine
) -> None:
    setup = submitted_application("Owner Secret Company")
    services = setup.services
    owner = actor_of(services)
    assert setup.analysis_id is not None
    assert setup.document_hash is not None

    private_fact = services.knowledge_lifecycle.create_pending_fact(
        owner,
        "situational_skills.json",
        {
            "meaning": "Owner Secret Fact",
            "renderings": {"en": "Owner Secret Fact"},
            "tags": ["situational"],
            "provenance": "explicit test fact",
            "resume_style": "bullet",
        },
    ).fact
    owner_operation = services.operation_submissions.submit_analysis(
        owner,
        AnalyzeCommand(
            application_id=setup.application_id,
            job_text_hash=setup.job_text_hash,
        ),
        idempotency_key="same-key-across-users",
        analysis_service=services.analysis,
    )
    owner_settings = services.settings.read(owner)
    services.settings.update(
        owner,
        owner_settings.edit_version,
        UpdateSettings(
            auto_generate_when_review_not_required=(
                owner_settings.auto_generate_when_review_not_required
            ),
            default_ai_model=owner_settings.default_ai_model,
            default_reasoning_effort=owner_settings.default_reasoning_effort,
            ui_density=owner_settings.ui_density,
            ui_text_size=owner_settings.ui_text_size,
            ui_theme="dark",
        ),
    )

    other_user = services.accounts.create_user(OTHER_EMAIL, OTHER_PASSWORD)
    services.knowledge_import.import_knowledge(OTHER_EMAIL, FileKnowledge(project_root))
    other = Actor(user_id=other_user.id)

    app = create_app(build_api_services(services))
    with TestClient(app) as client:
        login = client.post(
            f"{API_PREFIX}/auth/login",
            json={"email": OTHER_EMAIL, "password": OTHER_PASSWORD},
            headers=MUTATION_HEADERS,
        )
        assert login.status_code == 200, login.text
        client.headers["Cookie"] = f"{SESSION_COOKIE}={login.cookies[SESSION_COOKIE]}"

        action = {"expected_document_hash": setup.document_hash}
        cases = {
            ("POST", "/api/v1/analyses/{analysis_id}/apply-decisions"): ForeignRequest(
                "POST",
                f"{API_PREFIX}/analyses/{setup.analysis_id}/apply-decisions",
                {
                    "application_id": setup.application_id,
                    "expected_analysis_id": setup.analysis_id,
                    "expected_document_hash": setup.document_hash,
                },
            ),
            ("GET", "/api/v1/applications/{application_id}"): ForeignRequest(
                "GET", f"{API_PREFIX}/applications/{setup.application_id}"
            ),
            ("POST", "/api/v1/applications/{application_id}/analyses"): ForeignRequest(
                "POST",
                f"{API_PREFIX}/applications/{setup.application_id}/analyses",
                {"job_text_hash": setup.job_text_hash},
            ),
            ("POST", "/api/v1/applications/{application_id}/close"): ForeignRequest(
                "POST", f"{API_PREFIX}/applications/{setup.application_id}/close"
            ),
            ("POST", "/api/v1/applications/{application_id}/delete"): ForeignRequest(
                "POST", f"{API_PREFIX}/applications/{setup.application_id}/delete"
            ),
            ("GET", "/api/v1/applications/{application_id}/document"): ForeignRequest(
                "GET", f"{API_PREFIX}/applications/{setup.application_id}/document"
            ),
            ("PATCH", "/api/v1/applications/{application_id}/document"): ForeignRequest(
                "PATCH",
                f"{API_PREFIX}/applications/{setup.application_id}/document",
                {"claim_removals": ["foreign-claim"]},
                {"If-Match": f'"{setup.document_hash}"'},
            ),
            ("POST", "/api/v1/applications/{application_id}/document/approve"): ForeignRequest(
                "POST", f"{API_PREFIX}/applications/{setup.application_id}/document/approve", action
            ),
            (
                "POST",
                "/api/v1/applications/{application_id}/document/build-from-analysis",
            ): ForeignRequest(
                "POST",
                f"{API_PREFIX}/applications/{setup.application_id}/document/build-from-analysis",
                {**action, "analysis_id": setup.analysis_id},
            ),
            ("POST", "/api/v1/applications/{application_id}/document/check"): ForeignRequest(
                "POST", f"{API_PREFIX}/applications/{setup.application_id}/document/check", action
            ),
            (
                "GET",
                "/api/v1/applications/{application_id}/document/decision-markdown",
            ): ForeignRequest(
                "GET",
                f"{API_PREFIX}/applications/{setup.application_id}/document/decision-markdown",
            ),
            ("POST", "/api/v1/applications/{application_id}/document/draft"): ForeignRequest(
                "POST", f"{API_PREFIX}/applications/{setup.application_id}/document/draft", action
            ),
            ("GET", "/api/v1/applications/{application_id}/document/pdf"): ForeignRequest(
                "GET", f"{API_PREFIX}/applications/{setup.application_id}/document/pdf"
            ),
            ("GET", "/api/v1/applications/{application_id}/document/preview"): ForeignRequest(
                "GET", f"{API_PREFIX}/applications/{setup.application_id}/document/preview"
            ),
            ("GET", "/api/v1/applications/{application_id}/document/preview.pdf"): ForeignRequest(
                "GET", f"{API_PREFIX}/applications/{setup.application_id}/document/preview.pdf"
            ),
            (
                "POST",
                "/api/v1/applications/{application_id}/document/regenerate-claim",
            ): ForeignRequest(
                "POST",
                f"{API_PREFIX}/applications/{setup.application_id}/document/regenerate-claim",
                {**action, "claim_id": "foreign-claim"},
            ),
            (
                "POST",
                "/api/v1/applications/{application_id}/document/regenerate-section",
            ): ForeignRequest(
                "POST",
                f"{API_PREFIX}/applications/{setup.application_id}/document/regenerate-section",
                {**action, "section": "Experience"},
            ),
            ("POST", "/api/v1/applications/{application_id}/document/render"): ForeignRequest(
                "POST", f"{API_PREFIX}/applications/{setup.application_id}/document/render", action
            ),
            ("POST", "/api/v1/applications/{application_id}/external-submissions"): ForeignRequest(
                "POST",
                f"{API_PREFIX}/applications/{setup.application_id}/external-submissions",
                {"submitted_at": utc_now(), "metadata": {}},
            ),
            ("PATCH", "/api/v1/applications/{application_id}/job-text"): ForeignRequest(
                "PATCH",
                f"{API_PREFIX}/applications/{setup.application_id}/job-text",
                {"job_text": "foreign edit", "expected_job_text_hash": setup.job_text_hash},
            ),
            ("PATCH", "/api/v1/applications/{application_id}/next-action"): ForeignRequest(
                "PATCH",
                f"{API_PREFIX}/applications/{setup.application_id}/next-action",
                {"next_action": None, "next_action_date": None},
            ),
            ("PATCH", "/api/v1/applications/{application_id}/notes"): ForeignRequest(
                "PATCH",
                f"{API_PREFIX}/applications/{setup.application_id}/notes",
                {"notes": "foreign edit", "expected_notes": ""},
            ),
            ("POST", "/api/v1/applications/{application_id}/status"): ForeignRequest(
                "POST",
                f"{API_PREFIX}/applications/{setup.application_id}/status",
                {"target_status": "interview", "reason": "test"},
            ),
            ("POST", "/api/v1/applications/{application_id}/status-corrections"): ForeignRequest(
                "POST",
                f"{API_PREFIX}/applications/{setup.application_id}/status-corrections",
                {"target_status": "saved", "corrects_event_id": new_id(), "reason": "test"},
            ),
            ("POST", "/api/v1/applications/{application_id}/submissions"): ForeignRequest(
                "POST",
                f"{API_PREFIX}/applications/{setup.application_id}/submissions",
                {"expected_document_hash": setup.document_hash, "submitted_at": utc_now()},
            ),
            ("GET", "/api/v1/facts/{fact_id}"): ForeignRequest(
                "GET", f"{API_PREFIX}/facts/{private_fact.fact_id}"
            ),
            ("GET", "/api/v1/facts/attachment-targets"): ForeignRequest(
                "GET", f"{API_PREFIX}/facts/attachment-targets?fact_id={private_fact.fact_id}"
            ),
            ("POST", "/api/v1/facts/from-claim"): ForeignRequest(
                "POST",
                f"{API_PREFIX}/facts/from-claim",
                {
                    "application_id": setup.application_id,
                    "claim_id": "foreign-claim",
                    "source": "situational_skills.json",
                    "meaning": "foreign claim",
                    "tags": ["situational"],
                    "english": "foreign claim",
                    "provenance": "test",
                },
            ),
            ("POST", "/api/v1/facts/{fact_id}/attachments"): ForeignRequest(
                "POST",
                f"{API_PREFIX}/facts/{private_fact.fact_id}/attachments",
                {"profile": "account-manager", "section": "Experience", "pin": False},
            ),
            ("POST", "/api/v1/facts/{fact_id}/confirm"): ForeignRequest(
                "POST", f"{API_PREFIX}/facts/{private_fact.fact_id}/confirm", {"confirm": True}
            ),
            ("POST", "/api/v1/facts/{fact_id}/confirm-and-use"): ForeignRequest(
                "POST",
                f"{API_PREFIX}/facts/{private_fact.fact_id}/confirm-and-use",
                {
                    "application_id": setup.application_id,
                    "job_analysis_id": setup.analysis_id,
                    "profile": "account-manager",
                    "section": "Experience",
                },
            ),
            ("POST", "/api/v1/facts/{fact_id}/delete"): ForeignRequest(
                "POST", f"{API_PREFIX}/facts/{private_fact.fact_id}/delete", {"confirm": True}
            ),
            ("GET", "/api/v1/facts/{fact_id}/history"): ForeignRequest(
                "GET", f"{API_PREFIX}/facts/{private_fact.fact_id}/history"
            ),
            ("GET", "/api/v1/operations/{operation_id}"): ForeignRequest(
                "GET", f"{API_PREFIX}/operations/{owner_operation.id}"
            ),
            ("POST", "/api/v1/operations/{operation_id}/cancel"): ForeignRequest(
                "POST", f"{API_PREFIX}/operations/{owner_operation.id}/cancel"
            ),
            ("POST", "/api/v1/operations/{operation_id}/retry"): ForeignRequest(
                "POST", f"{API_PREFIX}/operations/{owner_operation.id}/retry"
            ),
        }

        assert set(cases) == _record_routes(app.openapi())
        before = persisted_counts(database_engine)
        for key, request in cases.items():
            headers = {"Origin": ALLOWED_ORIGIN, **(request.headers or {})}
            response = client.request(
                request.method, request.path, json=request.json, headers=headers
            )
            assert response.status_code == 404, (key, response.status_code, response.text)
            assert response.json()["code"] == "UNKNOWN_RECORD", key
            assert "Owner Secret" not in response.text, key
        assert persisted_counts(database_engine) == before

        listed = client.get(f"{API_PREFIX}/applications")
        assert listed.status_code == 200
        assert listed.json()["items"] == []
        assert listed.json()["matched"] == 0
        duplicate = client.post(
            f"{API_PREFIX}/applications/duplicate-check",
            json={
                "company": "Owner Secret Company",
                "target_role": "Account Manager",
                "job_text": "Owner Secret posting",
            },
            headers=MUTATION_HEADERS,
        )
        assert duplicate.status_code == 200
        assert duplicate.json() == {"matches": []}
        visible_facts = client.get(f"{API_PREFIX}/facts")
        assert visible_facts.status_code == 200
        assert private_fact.fact_id not in {
            item["fact"]["fact_id"] for item in visible_facts.json()["items"]
        }
        visible_settings = client.get(f"{API_PREFIX}/settings")
        assert visible_settings.status_code == 200
        assert visible_settings.json()["ui_theme"] == "system"

    other_application = services.applications.ingest(
        other,
        IngestCommand(
            company="Other Company",
            target_role="Account Manager",
            job_text="Other user's sufficiently detailed role description.",
            acknowledged_duplicates=True,
            client="web",
        ),
    )
    other_operation = services.operation_submissions.submit_analysis(
        other,
        AnalyzeCommand(
            application_id=other_application.application_id,
            job_text_hash=other_application.job_text_hash,
        ),
        idempotency_key="same-key-across-users",
        analysis_service=services.analysis,
    )
    assert other_operation.id != owner_operation.id

    with services_transactions(services).read() as tx:
        connection = services_transactions(services).connection_for(tx)
        shared_fact_id = connection.execute(
            select(facts.c.fact_id)
            .group_by(facts.c.fact_id)
            .having(func.count(func.distinct(facts.c.user_id)) == 2)
            .limit(1)
        ).scalar_one()
        assert (
            connection.execute(
                select(func.count()).select_from(facts).where(facts.c.fact_id == shared_fact_id)
            ).scalar_one()
            == 2
        )
