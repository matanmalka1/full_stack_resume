"""Token-scoped access to persisted safe application settings."""

from __future__ import annotations

from typing import Protocol

from ..settings import StoredSettings, UpdateSettings
from .transactions import ReadTransaction, WriteTransaction


class SettingsStore(Protocol):
    """What a consumer that only follows the settings may do: read them."""

    def settings(self, tx: ReadTransaction) -> StoredSettings: ...


class SettingsRepository(SettingsStore, Protocol):
    """What the settings service may do: read them and replace them."""

    def update_settings(
        self, tx: WriteTransaction, expected_edit_version: int, settings: UpdateSettings
    ) -> StoredSettings: ...
