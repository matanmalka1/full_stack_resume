from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cv_engine.canonical_data import write_canonical_sources


SOURCE_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def v1_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    write_canonical_sources(root / "base")
    for name in ("profiles", "rendering", "ai"):
        shutil.copytree(SOURCE_ROOT / name, root / name)
    return root
