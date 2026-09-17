"""Stateless token adapter for safe application settings reads."""

from __future__ import annotations

from sqlalchemy import select

from ...application.ports.transactions import ReadTransaction
from ...application.settings import StoredSettings
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
