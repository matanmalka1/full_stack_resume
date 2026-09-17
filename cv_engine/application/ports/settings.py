"""Token-scoped access to persisted safe application settings."""

from __future__ import annotations

from typing import Protocol

from ..settings import StoredSettings
from .transactions import ReadTransaction


class SettingsStore(Protocol):
    def settings(self, tx: ReadTransaction) -> StoredSettings: ...
