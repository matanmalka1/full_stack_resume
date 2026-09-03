from __future__ import annotations

from sqlalchemy import insert, select, update

from ...application.errors import StateConflict
from ...application.settings import StoredSettings, UpdateSettings
from ...util import utc_now
from .base import SqlAlchemyRepositoryBase
from .tables import app_settings


class SqlAlchemySettingsRepository(SqlAlchemyRepositoryBase):
    def app_settings(self) -> StoredSettings:
        with self.read_connection() as connection:
            row = (
                connection.execute(select(app_settings).where(app_settings.c.singleton_id == 1))
                .mappings()
                .one_or_none()
            )
        if row is None:
            return StoredSettings()
        return StoredSettings(
            edit_version=row["edit_version"],
            auto_generate_when_review_not_required=bool(
                row["auto_generate_when_review_not_required"]
            ),
            ai_enabled_override=(
                None if row["ai_enabled_override"] is None else bool(row["ai_enabled_override"])
            ),
            default_execution_mode=row["default_execution_mode"],
            default_ai_model=row["default_ai_model"],
            default_reasoning_effort=row["default_reasoning_effort"],
            ui_density=row["ui_density"],
            ui_text_size=row["ui_text_size"],
            updated_at=row["updated_at"],
        )

    def update_app_settings(
        self, expected_edit_version: int, settings: UpdateSettings
    ) -> StoredSettings:
        now = utc_now()
        with self.transaction() as connection:
            current = (
                connection.execute(
                    select(app_settings.c.edit_version).where(app_settings.c.singleton_id == 1)
                )
                .mappings()
                .one_or_none()
            )
            observed = 0 if current is None else current["edit_version"]
            if observed != expected_edit_version:
                raise StateConflict(
                    f"Application settings changed from version {expected_edit_version} "
                    f"to {observed}; reload them before saving"
                )
            next_version = observed + 1
            values = {
                "edit_version": next_version,
                "auto_generate_when_review_not_required": (
                    settings.auto_generate_when_review_not_required
                ),
                "ai_enabled_override": settings.ai_enabled_override,
                "default_execution_mode": settings.default_execution_mode,
                "default_ai_model": settings.default_ai_model,
                "default_reasoning_effort": settings.default_reasoning_effort,
                "ui_density": settings.ui_density,
                "ui_text_size": settings.ui_text_size,
                "updated_at": now,
            }
            if current is None:
                connection.execute(insert(app_settings).values(singleton_id=1, **values))
            else:
                connection.execute(
                    update(app_settings).where(app_settings.c.singleton_id == 1).values(**values)
                )
        return StoredSettings(
            edit_version=next_version,
            auto_generate_when_review_not_required=(
                settings.auto_generate_when_review_not_required
            ),
            ai_enabled_override=settings.ai_enabled_override,
            default_execution_mode=settings.default_execution_mode,
            default_ai_model=settings.default_ai_model,
            default_reasoning_effort=settings.default_reasoning_effort,
            ui_density=settings.ui_density,
            ui_text_size=settings.ui_text_size,
            updated_at=now,
        )
