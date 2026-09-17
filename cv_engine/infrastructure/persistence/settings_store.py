"""Stateless token adapter for safe application settings reads."""

from __future__ import annotations

from sqlalchemy import insert, select, update

from ...application.errors import StateConflict
from ...application.ports.transactions import ReadTransaction, WriteTransaction
from ...application.settings import StoredSettings, UpdateSettings
from ...util import utc_now
from .connection import SqlAlchemyTransactionManager
from .tables import app_settings


class SqlAlchemySettingsStore:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def settings(self, tx: ReadTransaction) -> StoredSettings:
        row = (
            self._transactions.connection_for(tx)
            .execute(select(app_settings).where(app_settings.c.singleton_id == 1))
            .mappings()
            .one_or_none()
        )
        if row is None:
            return StoredSettings()
        return StoredSettings(**{key: row[key] for key in StoredSettings.model_fields})

    def update_settings(
        self, tx: WriteTransaction, expected_edit_version: int, settings: UpdateSettings
    ) -> StoredSettings:
        connection = self._transactions.connection_for(tx, access="write")
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
        now = utc_now()
        next_version = observed + 1
        values = {
            "edit_version": next_version,
            "auto_generate_when_review_not_required": settings.auto_generate_when_review_not_required,
            "ai_enabled_override": settings.ai_enabled_override,
            "default_execution_mode": settings.default_execution_mode,
            "default_ai_model": settings.default_ai_model,
            "default_reasoning_effort": settings.default_reasoning_effort,
            "ui_density": settings.ui_density,
            "ui_text_size": settings.ui_text_size,
            "ui_theme": settings.ui_theme,
            "updated_at": now,
        }
        if current is None:
            connection.execute(insert(app_settings).values(singleton_id=1, **values))
        else:
            connection.execute(
                update(app_settings).where(app_settings.c.singleton_id == 1).values(**values)
            )
        return StoredSettings(**values)
