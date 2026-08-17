from __future__ import annotations

import shutil
from pathlib import Path

from ..application.ports import DraftPaths, RenderTargets, StoredDraft
from ..domain.drafts import parse_draft, seal_draft
from ..domain.models import DraftDocument
from ..runtime.workspace import Workspace


class FilesystemArtifactStore:
    """The Workspace's artifact layout, in one place.

    Every directory and file name the product uses for drafts, approved
    versions, and rendered output is decided here, so relocating storage is a
    change to this adapter rather than to the services that ask it for a
    location.
    """

    MARKDOWN = "resume.md"
    MANIFEST = "resume.claims.json"
    HTML = "resume.html"
    SCREENSHOT = "visual.png"

    def __init__(self, workspace: Workspace):
        self._workspace = workspace
        self._root = workspace.artifacts_root

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

    def render_targets(self, manifest_path: Path, pdf_filename: str) -> RenderTargets:
        """Where the rendered outputs of the version behind `manifest_path` go.

        They live beside the approved document they were rendered from, which
        is what makes "the PDF belongs to this exact version" checkable.
        """
        directory = manifest_path.parent
        return RenderTargets(
            html=directory / self.HTML,
            pdf=directory / pdf_filename,
            screenshot=directory / self.SCREENSHOT,
        )

    def resolve(self, stored_path: str) -> Path:
        return self._workspace.root / stored_path

    def relative(self, path: Path) -> str:
        return self._workspace.relative(path)
