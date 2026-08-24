from __future__ import annotations

from ...application.errors import StateConflict
from ...application.settings import StoredSettings, UpdateSettings
from ...util import utc_now
from .base import SqliteRepositoryBase


class SqliteSettingsRepository(SqliteRepositoryBase):
    def workspace_settings(self) -> StoredSettings:
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM workspace_settings WHERE singleton_id=1"
            ).fetchone()
        if row is None:
            return StoredSettings()
        return StoredSettings(
            edit_version=row["edit_version"],
            auto_generate_when_review_not_required=bool(
                row["auto_generate_when_review_not_required"]
            ),
            ai_enabled_override=(
                None
                if row["ai_enabled_override"] is None
                else bool(row["ai_enabled_override"])
            ),
            default_execution_mode=row["default_execution_mode"],
            open_browser_on_launch=bool(row["open_browser_on_launch"]),
            ui_density=row["ui_density"],
            ui_text_size=row["ui_text_size"],
            updated_at=row["updated_at"],
        )

    def update_workspace_settings(
        self, expected_edit_version: int, settings: UpdateSettings
    ) -> StoredSettings:
        now = utc_now()
        with self.transaction() as connection:
            current = connection.execute(
                "SELECT edit_version FROM workspace_settings WHERE singleton_id=1"
            ).fetchone()
            observed = 0 if current is None else current["edit_version"]
            if observed != expected_edit_version:
                raise StateConflict(
                    f"Workspace settings changed from version {expected_edit_version} "
                    f"to {observed}; reload them before saving"
                )
            next_version = observed + 1
            values = (
                next_version,
                int(settings.auto_generate_when_review_not_required),
                (
                    None
                    if settings.ai_enabled_override is None
                    else int(settings.ai_enabled_override)
                ),
                settings.default_execution_mode,
                int(settings.open_browser_on_launch),
                settings.ui_density,
                settings.ui_text_size,
                now,
            )
            if current is None:
                connection.execute(
                    "INSERT INTO workspace_settings("
                    "singleton_id, edit_version, auto_generate_when_review_not_required, "
                    "ai_enabled_override, default_execution_mode, open_browser_on_launch, "
                    "ui_density, ui_text_size, updated_at) VALUES(1, ?, ?, ?, ?, ?, ?, ?, ?)",
                    values,
                )
            else:
                connection.execute(
                    "UPDATE workspace_settings SET edit_version=?, "
                    "auto_generate_when_review_not_required=?, ai_enabled_override=?, "
                    "default_execution_mode=?, open_browser_on_launch=?, ui_density=?, "
                    "ui_text_size=?, updated_at=? WHERE singleton_id=1",
                    values,
                )
        return StoredSettings(
            edit_version=next_version,
            auto_generate_when_review_not_required=(
                settings.auto_generate_when_review_not_required
            ),
            ai_enabled_override=settings.ai_enabled_override,
            default_execution_mode=settings.default_execution_mode,
            open_browser_on_launch=settings.open_browser_on_launch,
            ui_density=settings.ui_density,
            ui_text_size=settings.ui_text_size,
            updated_at=now,
        )
