from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_legacy_status_check_treats_base_artifact_as_non_application() -> None:
    result = subprocess.run(
        [sys.executable, "check_status.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    if (ROOT / "data/applications.sqlite3").is_file():
        assert "v1 SQLite" in result.stdout
    else:
        assert "base CV artifact is intentionally not an application" in result.stdout
