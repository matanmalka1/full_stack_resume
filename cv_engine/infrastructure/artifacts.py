from __future__ import annotations

import shutil
from pathlib import Path
from typing import Protocol

from ..application.ports import DraftPaths, StoredDraft
from ..domain.contracts.drafts import DraftDocument
from ..domain.draft_markdown import parse_draft
from ..domain.drafts import seal_draft


class ArtifactPaths(Protocol):
    """The application paths this store uses.

    Declared here, as `PayloadStore` declares `PayloadPaths`, so an adapter
    does not import the composition layer that builds it. `relative` stays on
    the protocol rather than being replaced by a direct `relative_within` call:
    it carries the "must be absolute" containment check that
    artifact rows depend on, and `relative_within` alone would raise
    `ValueError`.
    """

    @property
    def root(self) -> Path: ...

    @property
    def artifacts_root(self) -> Path: ...

    def relative(self, path: Path) -> str: ...


class FilesystemArtifactStore:
    """The application's artifact layout, in one place.

    This compatibility adapter owns mutable working-draft paths and reads
    registered immutable payloads. New snapshot, revision, and rendered-output
    writes go through PayloadStore's approved layouts.
    """

    MARKDOWN = "resume.md"
    MANIFEST = "resume.claims.json"

    def __init__(self, paths: ArtifactPaths):
        self._paths = paths
        self._root = paths.artifacts_root

    def _pair(self, directory: Path) -> DraftPaths:
        return DraftPaths(directory / self.MARKDOWN, directory / self.MANIFEST)

    def working_paths(self, application_id: str) -> DraftPaths:
        return self._pair(self._root / "working" / application_id)

    def write_working_draft(self, draft: DraftDocument) -> StoredDraft:
        sealed, markdown, manifest = seal_draft(draft)
        paths = self.working_paths(sealed.application_id)
        paths.markdown.parent.mkdir(parents=True, exist_ok=True)
        paths.markdown.write_text(markdown, encoding="utf-8")
        paths.manifest.write_text(manifest, encoding="utf-8")
        return StoredDraft(paths, markdown)

    def load_working_draft(self, application_id: str) -> DraftDocument:
        return self.load_draft(self.working_paths(application_id).manifest)

    def working_markdown(self, application_id: str) -> str:
        return self.read_document(self.working_paths(application_id).markdown)

    def read_document(self, path: Path) -> str:
        """A stored document's text, or empty when it is not there.

        An absent document is not an error here: the caller's validation is
        what decides that a draft without its Markdown is invalid.
        """
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    def load_draft(self, manifest_path: Path) -> DraftDocument:
        return parse_draft(manifest_path.read_text(encoding="utf-8"))

    def paths_beside(self, manifest_path: Path) -> DraftPaths:
        """The document pair stored alongside a known manifest.

        Approved versions keep both payloads together, so a caller holding one
        recorded path can ask for the other without naming the file itself.
        """
        return self._pair(manifest_path.parent)

    def approved_version_dir(self, application_id: str, version: int) -> Path:
        return self._root / application_id / f"v{version:03d}"

    def publish_working_draft(self, application_id: str, version: int) -> DraftPaths:
        """Copy the working draft into a new immutable approved version.

        Refuses an existing directory rather than writing into it: an approved
        version that already exists is evidence, not a destination.
        """
        directory = self.approved_version_dir(application_id, version)
        if directory.exists():
            raise FileExistsError(f"approved version directory already exists: {directory}")
        directory.mkdir(parents=True)
        working = self.working_paths(application_id)
        published = self._pair(directory)
        shutil.copy2(working.markdown, published.markdown)
        shutil.copy2(working.manifest, published.manifest)
        return published

    def resolve(self, stored_path: str) -> Path:
        return self._paths.root / stored_path

    def relative(self, path: Path) -> str:
        return self._paths.relative(path)
