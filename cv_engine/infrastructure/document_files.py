"""The CV document's rendered files, and the immutable copies a Submission owns.

state-and-use-cases.md §16 and §18. A render writes to a unique per-attempt
directory under `<artifacts>/documents/<application>/<attempt>/`; those files are
mutable working outputs - the next render supersedes them, a re-pin releases them -
so they live outside every managed immutable layout and `payload_inventory` never
lists them. What was actually sent is copied into the payload store's
`submissions/` layout, hashed as it is stored.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

from ..application.errors import (
    ArtifactContainmentRefused,
    ArtifactPayloadMissing,
    InfrastructureFailure,
)
from ..application.ports.documents import RenderedFiles, SubmittedFiles
from ..application.ports.values import ArtifactStream, SnapshotPayload
from ..application.transactions import assert_external_io_allowed
from .paths import is_regular_file_within, relative_within, resolve_within


class DocumentFilePaths(Protocol):
    """The application paths this store uses, declared locally (see `PayloadPaths`)."""

    @property
    def root(self) -> Path: ...

    @property
    def artifacts_root(self) -> Path: ...


class SubmissionPayloads(Protocol):
    """The part of `PayloadStore` a Submission copy needs."""

    def submission_path(self, application_id: str, submission_id: str, *, suffix: str) -> Path: ...

    def reference_for(self, destination: Path) -> str: ...

    def commit_submission_file(
        self, application_id: str, submission_id: str, *, suffix: str, payload: bytes
    ) -> SnapshotPayload: ...


_STREAM_CHUNK_BYTES = 64 * 1024
_HTML = "resume.html"
_PDF = "resume.pdf"


def _component(value: str, *, name: str) -> str:
    candidate = Path(value)
    if (
        not value
        or value in {".", ".."}
        or candidate.is_absolute()
        or len(candidate.parts) != 1
        or candidate.name != value
    ):
        raise ValueError(f"invalid {name} path component: {value}")
    return value


class DocumentFiles:
    def __init__(self, paths: DocumentFilePaths, payloads: SubmissionPayloads):
        self._project_root = Path(paths.root).resolve()
        self._documents_root = resolve_within(
            self._project_root, Path(paths.artifacts_root) / "documents"
        )
        self._payloads = payloads

    def render_targets(self, application_id: str, attempt_id: str) -> tuple[Path, Path]:
        assert_external_io_allowed("document render target preparation")
        directory = resolve_within(
            self._documents_root,
            Path(
                _component(application_id, name="application_id"),
                _component(attempt_id, name="attempt_id"),
            ),
        )
        # `exist_ok=False`: an attempt directory is unique, so finding one already
        # there means two renders were handed the same attempt.
        directory.mkdir(parents=True, exist_ok=False)
        return directory / _HTML, directory / _PDF

    def reference_for(self, path: Path) -> str:
        relative_within(self._documents_root, path)
        return relative_within(self._project_root, path).as_posix()

    def _resolve(self, reference: str) -> Path:
        try:
            resolved = resolve_within(self._project_root, reference)
            relative_within(self._documents_root, resolved)
        except ValueError as exc:
            raise ArtifactContainmentRefused(
                "the document file reference does not resolve inside the document root"
            ) from exc
        return resolved

    def discard(self, files: RenderedFiles) -> None:
        assert_external_io_allowed("document render file removal")
        directories: set[Path] = set()
        for reference in (files.html, files.pdf):
            try:
                path = self._resolve(reference)
            except ArtifactContainmentRefused:
                continue
            try:
                path.unlink(missing_ok=True)
            except OSError:
                continue
            directories.add(path.parent)
        for directory in directories:
            try:
                directory.rmdir()
            except OSError:
                # Best-effort: a directory still holding something is left alone.
                pass

    def _read(self, reference: str) -> bytes:
        path = self._resolve(reference)
        if not is_regular_file_within(self._documents_root, path):
            raise ArtifactPayloadMissing("the document's rendered file is not stored")
        try:
            return path.read_bytes()
        except FileNotFoundError as exc:
            raise ArtifactPayloadMissing("the document's rendered file is not stored") from exc
        except OSError as exc:
            raise InfrastructureFailure("the document's rendered file could not be read") from exc

    def open_rendered_pdf(self, reference: str) -> ArtifactStream:
        assert_external_io_allowed("document PDF read")
        payload = self._read(reference)

        def chunks() -> Iterator[bytes]:
            for offset in range(0, len(payload), _STREAM_CHUNK_BYTES):
                yield payload[offset : offset + _STREAM_CHUNK_BYTES]

        return ArtifactStream(size=len(payload), chunks=chunks)

    def submission_targets(self, application_id: str, submission_id: str) -> tuple[str, str]:
        """The references a Submission's two copies will receive, without writing."""
        return (
            self._payloads.reference_for(
                self._payloads.submission_path(application_id, submission_id, suffix="html")
            ),
            self._payloads.reference_for(
                self._payloads.submission_path(application_id, submission_id, suffix="pdf")
            ),
        )

    def copy_for_submission(
        self, application_id: str, submission_id: str, files: RenderedFiles
    ) -> SubmittedFiles:
        """Copy the rendered files into the Submission's immutable layout.

        The payload write lease is the caller's: it is acquired against
        `submission_targets` before this runs and marked committed in the same
        transaction that inserts the Submission.
        """
        assert_external_io_allowed("submission file copy")
        html = self._payloads.commit_submission_file(
            application_id, submission_id, suffix="html", payload=self._read(files.html)
        )
        pdf = self._payloads.commit_submission_file(
            application_id, submission_id, suffix="pdf", payload=self._read(files.pdf)
        )
        return SubmittedFiles(
            html_path=html.reference,
            html_sha256=html.sha256,
            pdf_path=pdf.reference,
            pdf_sha256=pdf.sha256,
        )
