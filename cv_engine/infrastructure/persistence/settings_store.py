"""Stateless token adapter for one user's safe settings (`user_settings`)."""

from __future__ import annotations

from sqlalchemy import insert, select, update

from ...application.errors import StateConflict
from ...application.ports.transactions import ReadTransaction, WriteTransaction
from ...application.settings import StoredSettings, UpdateSettings
from ...util import utc_now
from .connection import SqlAlchemyTransactionManager
from .tables import user_settings


class SqlAlchemySettingsStore:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def settings(self, tx: ReadTransaction, user_id: str) -> StoredSettings:
        row = (
            self._transactions.connection_for(tx)
            .execute(select(user_settings).where(user_settings.c.user_id == user_id))
            .mappings()
            .one_or_none()
        )
        if row is None:
            return StoredSettings()
        return StoredSettings(**{key: row[key] for key in StoredSettings.model_fields})

    def update_settings(
        self,
        tx: WriteTransaction,
        user_id: str,
        expected_edit_version: int,
        settings: UpdateSettings,
    ) -> StoredSettings:
        connection = self._transactions.connection_for(tx, access="write")
        current = (
            connection.execute(
                select(user_settings.c.edit_version).where(user_settings.c.user_id == user_id)
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
            "default_ai_model": settings.default_ai_model,
            "default_reasoning_effort": settings.default_reasoning_effort,
            "ui_density": settings.ui_density,
            "ui_text_size": settings.ui_text_size,
            "ui_theme": settings.ui_theme,
            "default_template": settings.default_template,
            "updated_at": now,
        }
        if current is None:
            connection.execute(insert(user_settings).values(user_id=user_id, **values))
        else:
            connection.execute(
                update(user_settings).where(user_settings.c.user_id == user_id).values(**values)
            )
        return StoredSettings(**values)
