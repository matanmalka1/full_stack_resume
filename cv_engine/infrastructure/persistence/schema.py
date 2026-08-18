from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...util import sha256_text, utc_now
from .connection import connect, memory_connection


MIGRATIONS_DIR = Path(__file__).with_name("migrations")
REGISTERED_MIGRATIONS = (
    "0001_baseline.sql",
    "0002_preparation_records.sql",
    "0003_snapshot_payload_cutover.sql",
)
SCHEMA_VERSION = "2"


class SchemaError(RuntimeError):
    """Base class for a refused schema open or migration."""


class SchemaFingerprintError(SchemaError):
    """An unstamped database is not the exact adoptable M1 baseline."""


class SchemaVersionError(SchemaError):
    """The database migration version cannot be opened by this code."""


class MigrationChecksumError(SchemaError):
    """An already-applied migration no longer has its recorded bytes."""


@dataclass(frozen=True)
class Migration:
    version: str
    name: str
    sql: str
    checksum: str


def registered_migration_names() -> list[str]:
    return list(REGISTERED_MIGRATIONS)


def _migration_files(migration_dir: Path = MIGRATIONS_DIR) -> list[Path]:
    files = sorted(migration_dir.glob("*.sql"))
    names = [path.name for path in files]
    if names != registered_migration_names():
        raise SchemaError(
            "migration files and registry differ: "
            f"files={names}, registered={registered_migration_names()}"
        )
    versions = [name.split("_", 1)[0] for name in names]
    if len(versions) != len(set(versions)):
        raise SchemaError(f"duplicate migration version: {versions}")
    return files


def migrations(migration_dir: Path = MIGRATIONS_DIR) -> list[Migration]:
    result: list[Migration] = []
    for path in _migration_files(migration_dir):
        sql = path.read_text(encoding="utf-8")
        result.append(
            Migration(
                version=path.name.split("_", 1)[0],
                name=path.name,
                sql=sql,
                checksum=sha256_text(sql),
            )
        )
    return result


def _bootstrap(connection: Any) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version TEXT PRIMARY KEY, name TEXT NOT NULL, checksum TEXT NOT NULL, "
        "applied_at TEXT NOT NULL)"
    )


def _has_table(connection: Any, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _has_user_schema(connection: Any) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE sql IS NOT NULL "
        "AND name NOT LIKE 'sqlite_%' LIMIT 1"
    ).fetchone() is not None


def sqlite_master_fingerprint(connection: Any) -> list[tuple[str, str, str, str]]:
    """Return normalized M1-owned DDL, excluding migration bookkeeping."""
    rows = connection.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master "
        "WHERE sql IS NOT NULL AND name != 'schema_migrations' "
        "ORDER BY type, name"
    ).fetchall()
    return [
        (row[0], row[1], row[2], " ".join(row[3].split()))
        for row in rows
    ]


def baseline_fingerprint(migration_dir: Path = MIGRATIONS_DIR) -> list[tuple[str, str, str, str]]:
    baseline = migrations(migration_dir)[0]
    connection = memory_connection()
    try:
        connection.executescript(baseline.sql)
        return sqlite_master_fingerprint(connection)
    finally:
        connection.close()


def _fingerprint_difference(
    expected: list[tuple[str, str, str, str]],
    actual: list[tuple[str, str, str, str]],
) -> str:
    expected_by_name = {(kind, name): ddl for kind, name, _table, ddl in expected}
    actual_by_name = {(kind, name): ddl for kind, name, _table, ddl in actual}
    missing = sorted(set(expected_by_name) - set(actual_by_name))
    extra = sorted(set(actual_by_name) - set(expected_by_name))
    changed = sorted(
        key
        for key in set(expected_by_name) & set(actual_by_name)
        if expected_by_name[key] != actual_by_name[key]
    )
    return f"missing={missing}, extra={extra}, changed={changed}"


def _adopt_baseline(connection: Any, available: list[Migration]) -> None:
    expected = baseline_fingerprint()
    actual = sqlite_master_fingerprint(connection)
    if actual != expected:
        raise SchemaFingerprintError(
            "existing database does not match the adoptable 0001 baseline: "
            + _fingerprint_difference(expected, actual)
        )
    _bootstrap(connection)
    baseline = available[0]
    connection.execute(
        "INSERT INTO schema_migrations(version, name, checksum, applied_at) "
        "VALUES(?, ?, ?, ?)",
        (baseline.version, baseline.name, baseline.checksum, utc_now()),
    )
    connection.commit()


def _applied(connection: Any) -> list[Any]:
    return connection.execute(
        "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
    ).fetchall()


def _verify_applied(applied: list[Any], available: list[Migration]) -> None:
    known = {migration.version: migration for migration in available}
    for row in applied:
        version = row["version"]
        migration = known.get(version)
        if migration is None or migration.name != row["name"]:
            raise SchemaVersionError(
                f"database has unknown or newer schema migration {version} ({row['name']})"
            )
        if migration.checksum != row["checksum"]:
            raise MigrationChecksumError(
                f"applied migration checksum changed: {migration.name}"
            )
    expected_prefix = [migration.version for migration in available[: len(applied)]]
    actual_versions = [row["version"] for row in applied]
    if actual_versions != expected_prefix:
        raise SchemaVersionError(
            f"database migrations are not an ordered prefix: {actual_versions}"
        )


def _apply_one(connection: Any, migration: Migration) -> None:
    try:
        connection.executescript("BEGIN IMMEDIATE;\n" + migration.sql)
        connection.execute(
            "INSERT INTO schema_migrations(version, name, checksum, applied_at) "
            "VALUES(?, ?, ?, ?)",
            (migration.version, migration.name, migration.checksum, utc_now()),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def apply_migrations(path: Path) -> str:
    """Explicitly apply all pending registered migrations in order."""
    available = migrations()
    connection = connect(path)
    try:
        if _has_user_schema(connection) and not _has_table(connection, "schema_migrations"):
            _adopt_baseline(connection, available)
        else:
            _bootstrap(connection)
            connection.commit()
        applied = _applied(connection)
        _verify_applied(applied, available)
        for migration in available[len(applied) :]:
            _apply_one(connection, migration)
        return available[-1].version
    finally:
        connection.close()


def ensure_current_schema(path: Path) -> str:
    """Create a new database or fail closed unless an existing one is current."""
    path = Path(path)
    existed_with_bytes = path.exists() and path.stat().st_size > 0
    if not existed_with_bytes:
        return apply_migrations(path)

    available = migrations()
    connection = connect(path)
    try:
        if not _has_table(connection, "schema_migrations"):
            _adopt_baseline(connection, available)
        applied = _applied(connection)
        _verify_applied(applied, available)
        if len(applied) < len(available):
            current = applied[-1]["version"] if applied else "none"
            raise SchemaVersionError(
                f"database schema {current} is older than code schema "
                f"{available[-1].version}; run `cv workspace upgrade` explicitly"
            )
        return applied[-1]["version"]
    finally:
        connection.close()


def current_schema_version(path: Path) -> str | None:
    if not Path(path).exists():
        return None
    connection = connect(path)
    try:
        if not _has_table(connection, "schema_migrations"):
            return None
        row = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1"
        ).fetchone()
        return None if row is None else row["version"]
    finally:
        connection.close()


def initialize(path: Path) -> None:
    """Compatibility entry point: create or version-gate, never silently upgrade."""
    ensure_current_schema(path)
