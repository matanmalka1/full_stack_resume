from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..application.ports import DraftPaths, StoredDraft
from ..application.transactions import assert_external_io_allowed
from ..domain.contracts.drafts import DraftDocument
from ..domain.drafts import seal_draft


class ArtifactPaths(Protocol):
    """The application paths this store uses.

    Declared here, as `PayloadStore` declares `PayloadPaths`, so an adapter
    does not import the composition layer that builds it.
    """

    @property
    def artifacts_root(self) -> Path: ...


class FilesystemArtifactStore:
    """The application's artifact layout, in one place.

    Owns mutable working-draft projections. Immutable snapshot, revision, and
    rendered-output writes go through PayloadStore's approved layouts.
    """

    MARKDOWN = "resume.md"
    MANIFEST = "resume.claims.json"

    def __init__(self, paths: ArtifactPaths):
        self._root = paths.artifacts_root

    def _pair(self, directory: Path) -> DraftPaths:
        return DraftPaths(directory / self.MARKDOWN, directory / self.MANIFEST)

    def _working_paths(self, application_id: str) -> DraftPaths:
        return self._pair(self._root / "working" / application_id)

    def write_working_draft(self, draft: DraftDocument) -> StoredDraft:
        assert_external_io_allowed("working projection write")
        sealed, markdown, manifest = seal_draft(draft)
        paths = self._working_paths(sealed.application_id)
        paths.markdown.parent.mkdir(parents=True, exist_ok=True)
        paths.markdown.write_text(markdown, encoding="utf-8")
        paths.manifest.write_text(manifest, encoding="utf-8")
        return StoredDraft(paths, markdown)
