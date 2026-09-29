"""React -> real HTTP -> PostgreSQL, with no provider or API interception."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

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


def test_browser_intake_persists_and_requires_duplicate_acknowledgement(live_api_server) -> None:
    # The shared fixtures supply an empty, migrated test database and a temporary
    # knowledge root. The API serves React on its own origin, as in production.
    assert os.environ.get("OPENAI_API_KEY") is None
    result = subprocess.run(
        [
            "node",
            "node_modules/@playwright/test/cli.js",
            "test",
            "--config",
            "playwright.integration.config.ts",
        ],
        cwd=FRONTEND,
        env={**os.environ, "CV_TEST_BASE_URL": live_api_server.base_url},
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
