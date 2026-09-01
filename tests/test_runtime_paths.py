from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import _isolated_database_url

from cv_engine.runtime.config import CONFIG_NAME, ConfigError, parse_env_file, resolve_config
from cv_engine.runtime.paths import AppPaths, PathConfigurationError


def test_application_paths_are_fixed_below_the_project_root(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    paths = AppPaths.from_root(root)

    assert paths.root == root.resolve()
    assert paths.knowledge_root == root.resolve()
    assert paths.artifacts_root == root.resolve() / "artifacts"
    assert paths.temp_root == root.resolve() / "tmp"
    assert paths.logs_root == root.resolve() / "logs"
    assert paths.relative(paths.artifacts_root / "a.pdf") == "artifacts/a.pdf"


def test_application_paths_refuse_relative_and_external_paths(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    paths = AppPaths.from_root(root)

    with pytest.raises(PathConfigurationError, match="outside the project root"):
        paths.relative(Path("artifacts/a.pdf"))
    with pytest.raises(PathConfigurationError, match="outside the project root"):
        paths.relative(tmp_path / "elsewhere.pdf")


def test_project_config_precedence_and_validation(tmp_path: Path) -> None:
    (tmp_path / CONFIG_NAME).write_text(json.dumps({"model": "stored-model"}), encoding="utf-8")
    (tmp_path / ".env").write_text("CV_MODEL=env-file-model\n", encoding="utf-8")

    stored = resolve_config(env={}, project_root=tmp_path)
    assert (stored.get("model"), stored.source("model")) == ("env-file-model", "env-file")

    environment = resolve_config(env={"CV_MODEL": "env-model"}, project_root=tmp_path)
    assert (environment.get("model"), environment.source("model")) == (
        "env-model",
        "environment",
    )

    (tmp_path / CONFIG_NAME).write_text(json.dumps({"unknown": True}), encoding="utf-8")
    with pytest.raises(ConfigError, match="unknown project config settings"):
        resolve_config(env={}, project_root=tmp_path)

    (tmp_path / CONFIG_NAME).write_text(
        json.dumps({"openai_api_key": "must-not-load"}), encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="unknown project config settings"):
        resolve_config(env={}, project_root=tmp_path)


def test_env_file_precedence_secrets_and_parsing(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "CV_DATABASE_URL=postgresql+psycopg://cv:filepw@127.0.0.1:5433/fromfile\n"
        "CV_MODEL=model-from-file\n"
        "OPENAI_API_KEY=must-not-load\n",
        encoding="utf-8",
    )
    resolved = resolve_config(env={}, project_root=tmp_path)
    assert (resolved.get("model"), resolved.source("model")) == (
        "model-from-file",
        "env-file",
    )
    assert resolved.get("openai_api_key") is None
    assert resolved.describe()["database_url"]["value"] == "***"
    assert parse_env_file("\n# note\nexport A=1\nB='two'\ninvalid\n") == {
        "A": "1",
        "B": "two",
    }


def test_the_suite_never_runs_against_the_configured_runtime_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The guard that keeps a test run out of the developer's own database.

    Every fixture TRUNCATEs the whole schema, so reading the configured URL
    directly meant a run emptied the running system and left its last test's
    rows behind - orphan `artifact_versions` pointing into a deleted tmp root.
    """
    configured = "postgresql+psycopg://cv:cv@127.0.0.1:5433/cv"

    monkeypatch.delenv("CV_TEST_DATABASE_URL", raising=False)
    assert _isolated_database_url(configured).endswith("/cv_test")
    assert _isolated_database_url(configured + "_test").endswith("/cv_test")

    monkeypatch.setenv("CV_TEST_DATABASE_URL", "postgresql+psycopg://cv:cv@127.0.0.1:5433/other")
    assert _isolated_database_url(configured).endswith("/other")

    monkeypatch.setenv("CV_TEST_DATABASE_URL", configured)
    with pytest.raises(RuntimeError, match="configured runtime database"):
        _isolated_database_url(configured)
