"""React -> real HTTP -> PostgreSQL and the worker, without API interception."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from threading import Event, Thread

import pytest
from helpers import analysis_proposal

from cv_engine.domain.contracts.analysis_proposal import ProposedRequirement

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
pytestmark = pytest.mark.browser


@pytest.fixture
def frontend_dist(tmp_path: Path) -> Path:
    """Build before uvicorn starts; never serve a stale developer dist directory."""
    build_dir = tmp_path / "frontend-dist"
    result = subprocess.run(
        ["npm", "run", "build", "--", "--outDir", str(build_dir)],
        cwd=FRONTEND,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return build_dir


def run_browser(live_api_server, spec: str) -> None:
    assert os.environ.get("OPENAI_API_KEY") is None
    result = subprocess.run(
        [
            "node",
            "node_modules/@playwright/test/cli.js",
            "test",
            "--config",
            "playwright.integration.config.ts",
            spec,
        ],
        cwd=FRONTEND,
        env={**os.environ, "CV_TEST_BASE_URL": live_api_server.base_url},
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_browser_intake_persists_and_requires_duplicate_acknowledgement(live_api_server) -> None:
    # Each test owns an empty, migrated database and a temporary knowledge root.
    run_browser(live_api_server, "intake.spec.ts")


@pytest.mark.parametrize("live_api_factory", ["asgi_factory:build_test_ai_app"], indirect=True)
def test_browser_analysis_through_ready_and_submission(
    live_api_server, ai_services, fake_openai
) -> None:
    # Only the provider transport is scripted. The API is a separate uvicorn
    # process; the real worker runs here, sharing its PostgreSQL database and
    # temporary artifact root. Rendering uses real Chromium, not a fake PDF.
    fake_openai.script(
        "propose_analysis",
        analysis_proposal(
            requirements=[
                ProposedRequirement(
                    text=quote,
                    importance="mandatory",
                    coverage="matched",
                    fact_ids=[fact_id],
                    rationale="stated in the posting",
                )
                for quote, fact_id in (
                    ("Experience owning the full sales cycle.", "sales.summary.new_business"),
                    ("Fluent English.", "common.language.english"),
                )
            ]
        ),
    )
    stop = Event()
    worker = Thread(target=ai_services.operation_worker.serve, args=(stop,), daemon=True)
    worker.start()
    try:
        run_browser(live_api_server, "preparation.spec.ts")
        assert [call.task for call in fake_openai.calls] == ["propose_analysis"]
    finally:
        stop.set()
        worker.join(timeout=15)
        assert not worker.is_alive(), "the browser journey worker did not stop"
