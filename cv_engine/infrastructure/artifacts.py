from __future__ import annotations

import shutil
from pathlib import Path

from ..application.ports import DraftPaths
from ..domain.drafts import load_draft, write_working_draft
from ..domain.models import DraftDocument
from ..runtime.workspace import Workspace


class FilesystemArtifactStore:
    """The Workspace's artifact layout, in one place.

    Every directory name the product uses for drafts and approved versions is
    decided here, so relocating storage is a change to this adapter rather than
    to the services that ask it for a location.
    """

    def __init__(self, workspace: Workspace):
        self._workspace = workspace
        self._root = workspace.artifacts_root

    def working_paths(self, application_id: str) -> DraftPaths:
        directory = self._root / "working" / application_id
        return DraftPaths(directory / "resume.md", directory / "resume.claims.json")

    def write_working_draft(self, draft: DraftDocument) -> DraftPaths:
        markdown, manifest = write_working_draft(self._root, draft)
        return DraftPaths(markdown, manifest)

    def load_working_draft(self, application_id: str) -> DraftDocument:
        return load_draft(self.working_paths(application_id).manifest)

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
        published = DraftPaths(directory / "resume.md", directory / "resume.claims.json")
        shutil.copy2(working.markdown, published.markdown)
        shutil.copy2(working.manifest, published.manifest)
        return published

    def resolve(self, stored_path: str) -> Path:
        return self._workspace.root / stored_path

    def relative(self, path: Path) -> str:
        return self._workspace.relative(path)
