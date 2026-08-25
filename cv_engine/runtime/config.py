from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONFIG_NAME = "cv.config.json"


class ConfigError(RuntimeError):
    """Runtime configuration could not be read safely."""


@dataclass(frozen=True)
class Setting:
    """One configurable value and where it may come from.

    `secret` marks a value that carries a credential. It changes nothing about
    how the value is read or used - only how it is displayed. Masking happens
    at the display boundary, never in the value handed to a connector: a
    masked URL that reached `create_engine` would be a connection string
    pointing at a host called `***`.

    `environment_only` refuses file-backed layers for one setting, so it can be
    supplied by a real environment variable and nothing else. It exists for
    `OPENAI_API_KEY`. Everything in this repository - `CLAUDE.md`,
    `docs/v2/smoke-run.md`, and every test that asserts the offline path -
    treats "the variable is unset" as "no provider is configured". A `.env`
    able to supply the key would silently break that equivalence: `unset
    OPENAI_API_KEY` would no longer disarm AI, because unset is not the same
    as overridden, and a developer who forgot a file would spend money without
    knowing. Keeping the key out of files also keeps it out of the place
    credentials actually leak from, which is a committed file.
    """

    name: str
    env: str
    default: Any = None
    secret: bool = False
    environment_only: bool = False


# The HTTP body limit lives here rather than in the API package because the
# test plan (§10) requires the chosen value to be recorded in the config
# contract and can be reported by diagnostics.
# 2 MiB sits inside the approved 1-2 MB order of magnitude.
API_MAX_BODY_BYTES_DEFAULT = 2 * 1024 * 1024

SETTINGS: dict[str, Setting] = {
    setting.name: setting
    for setting in (
        Setting(
            "database_url",
            "CV_DATABASE_URL",
            default="postgresql+psycopg://cv:cv@127.0.0.1:5433/cv",
            secret=True,
        ),
        Setting("provider", "CV_PROVIDER", default="deterministic"),
        Setting("model", "CV_MODEL", default="gpt-5.6"),
        # Read through the config contract rather than from `os.environ` at the
        # point of use, so that one layer decides where a credential comes from
        # and one flag decides how it is shown. Absent means no AI adapter is
        # built at all, which is what keeps the deterministic workflow reaching
        # Ready with nothing configured - and `environment_only` is what keeps
        # `unset OPENAI_API_KEY` sufficient to mean absent.
        Setting(
            "openai_api_key",
            "OPENAI_API_KEY",
            default=None,
            secret=True,
            environment_only=True,
        ),
        Setting("api_max_body_bytes", "CV_API_MAX_BODY_BYTES", default=API_MAX_BODY_BYTES_DEFAULT),
        # Unset in production: the built UI is served same-origin, so there is no
        # second origin to allow. A value here is the one development Vite origin
        # and nothing else — never a wildcard, never a list.
        Setting("api_dev_origin", "CV_API_DEV_ORIGIN", default=None),
        # Immutable payload storage. "local" is the default and keeps every
        # payload below the application root; "s3" stores them in a bucket,
        # which is what a deployed installation uses. Nothing else about the
        # workflow changes - the reference strings recorded in
        # `artifact_versions` are identical either way.
        Setting("object_store", "CV_OBJECT_STORE", default="local"),
        Setting("s3_bucket", "CV_S3_BUCKET", default=None),
        Setting("s3_prefix", "CV_S3_PREFIX", default=None),
        # Set for R2 or MinIO; unset for AWS S3, where boto3 derives the
        # endpoint from the region.
        Setting("s3_endpoint_url", "CV_S3_ENDPOINT_URL", default=None),
        Setting("s3_region", "CV_S3_REGION", default=None),
    )
}

ENV_FILE_NAME = ".env"
MASK = "***"


def parse_env_file(text: str) -> dict[str, str]:
    """Parse the small `KEY=value` subset a `.env` file actually needs.

    Deliberately not `python-dotenv`: the supported surface here is one
    assignment per line, `#` comments, optional `export ` prefixes, and
    single- or double-quoted values. A dependency would buy shell-style
    interpolation and multi-line values, neither of which any setting in
    `SETTINGS` can hold.

    A malformed line is skipped rather than raised on. A `.env` is developer
    convenience, and refusing to start because of a stray line in a file that
    the real environment can override anyway would be the wrong trade.
    """
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, separator, value = line.partition("=")
        if not separator:
            continue
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        values[key] = value
    return values


def load_env_file(path: Path) -> dict[str, str]:
    """Read one `.env` file, or nothing if it is absent or unreadable."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    return parse_env_file(text)


def env_file_path(project_root: Path | None) -> Path | None:
    """Return the single project-root `.env` considered for this run."""
    return None if project_root is None else Path(project_root) / ENV_FILE_NAME


def mask_value(name: str, value: Any) -> Any:
    """The display form of one setting's value.

    An unset secret shows as `None`, not as `***`: "no key is configured" and
    "a key is configured and withheld" are different facts, and collapsing
    them would hide the one that explains why AI mode is off.
    """
    setting = SETTINGS.get(name)
    if setting is None or not setting.secret or value is None or value == "":
        return value
    return MASK


SOURCES = ("cli", "environment", "env-file", "project-config", "default")


@dataclass(frozen=True)
class Resolved:
    value: Any
    source: str


class RuntimeConfig:
    """Resolved settings plus the layer each one came from.

    The source is kept so diagnostics can answer "why is this value in effect",
    and because a setting silently arriving from
    an unexpected layer is the kind of thing that only shows up as a wrong
    artifact much later.
    """

    def __init__(self, values: dict[str, Resolved]):
        self.values = values

    def get(self, name: str) -> Any:
        return self.values[name].value

    def source(self, name: str) -> str:
        return self.values[name].source

    def describe(self) -> dict[str, dict[str, Any]]:
        """The reportable form: secret values masked, sources intact.

        `source` is never masked. Knowing a credential arrived from the
        environment rather than a `.env` is exactly what makes a stale value
        diagnosable, and it reveals nothing about the value itself.
        """
        return {
            name: {"value": mask_value(name, resolved.value), "source": resolved.source}
            for name, resolved in sorted(self.values.items())
        }


def load_project_config(root: Path) -> dict[str, Any]:
    path = Path(root) / CONFIG_NAME
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"unreadable project config {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ConfigError(f"project config must be an object: {path}")
    allowed = {name for name, setting in SETTINGS.items() if not setting.environment_only}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ConfigError(f"unknown project config settings in {path}: {', '.join(unknown)}")
    return payload


def resolve_config(
    *,
    cli: Mapping[str, Any] | None = None,
    env: Mapping[str, str] | None = None,
    project_root: Path | None = None,
    env_file: Mapping[str, str] | None = None,
) -> RuntimeConfig:
    """Apply CLI > environment > project `.env` > project config > default.

    The `.env` layer sits below the real environment on purpose: a value a
    developer exported deliberately in this shell must not be silently
    overridden by a file they last edited weeks ago. The reverse order is how
    a stale file becomes a defect that reads as a code bug.

    A setting marked `environment_only` skips that layer entirely: see
    `Setting` for why `OPENAI_API_KEY` must not be suppliable by a file.

    `env_file` may be passed directly, which is what lets a caller resolve
    against a known mapping without touching the filesystem.
    """
    cli = cli or {}
    env = env if env is not None else {}
    if env_file is None:
        path = env_file_path(project_root)
        env_file = load_env_file(path) if path is not None else {}
    stored = load_project_config(project_root) if project_root is not None else {}
    values: dict[str, Resolved] = {}
    for name, setting in SETTINGS.items():
        if cli.get(name) is not None:
            values[name] = Resolved(cli[name], "cli")
        elif env.get(setting.env):
            values[name] = Resolved(env[setting.env], "environment")
        elif not setting.environment_only and env_file.get(setting.env):
            values[name] = Resolved(env_file[setting.env], "env-file")
        elif not setting.environment_only and stored.get(name) is not None:
            values[name] = Resolved(stored[name], "project-config")
        else:
            values[name] = Resolved(setting.default, "default")
    return RuntimeConfig(values)
