from __future__ import annotations

import json
import os
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..application.ports import RevisionPayloads, SnapshotPayload
from ..util import sha256_file
from .paths import relative_within, resolve_within


class PayloadWorkspace(Protocol):
    root: Path
    artifacts_root: Path
    temp_root: Path


PayloadWriter = Callable[[Path], None]
PayloadValidator = Callable[[Path], bool | None]


@dataclass(frozen=True, slots=True)
class StoredPayload:
    path: Path
    workspace_relative: str
    sha256: str
    size: int


@dataclass(frozen=True, slots=True)
class TempOrphan:
    path: Path
    workspace_relative: str
    age_seconds: float
    size: int


@dataclass(frozen=True)
class _PayloadRoots:
    root: Path
    artifacts_root: Path
    temp_root: Path


class PayloadStore:
    """Immutable v2 payload storage, independent of SQLite registration."""

    _OUTPUT_SUFFIXES = {".html", ".pdf", ".png"}
    _TEMP_DIRECTORY = "payloads"

    def __init__(self, workspace: PayloadWorkspace):
        self._workspace_root = Path(workspace.root).resolve()
        self._artifacts_root = resolve_within(
            self._workspace_root, workspace.artifacts_root
        )
        self._temp_root = resolve_within(self._workspace_root, workspace.temp_root)

    @classmethod
    def for_workspace_root(cls, root: Path) -> "PayloadStore":
        resolved = Path(root).resolve()
        return cls(_PayloadRoots(
            root=resolved,
            artifacts_root=resolved / "artifacts",
            temp_root=resolved / "tmp",
        ))

    @staticmethod
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

    def _target(self, *parts: str) -> Path:
        return resolve_within(self._artifacts_root, Path(*parts))

    def snapshot_path(self, application_id: str, snapshot_id: str) -> Path:
        return self._target(
            "snapshots",
            self._component(application_id, name="application_id"),
            f"{self._component(snapshot_id, name='snapshot_id')}.txt",
        )

    def revision_path(
        self, application_id: str, revision_id: str, *, format: str
    ) -> Path:
        if format not in {"json", "md"}:
            raise ValueError(f"unsupported revision format: {format}")
        return self._target(
            "revisions",
            self._component(application_id, name="application_id"),
            self._component(revision_id, name="revision_id"),
            f"resume.{format}",
        )

    def output_path(
        self,
        application_id: str,
        revision_id: str,
        artifact_id: str,
        *,
        suffix: str,
    ) -> Path:
        normalized_suffix = suffix if suffix.startswith(".") else f".{suffix}"
        if normalized_suffix not in self._OUTPUT_SUFFIXES:
            raise ValueError(f"unsupported output suffix: {suffix}")
        return self._target(
            "outputs",
            self._component(application_id, name="application_id"),
            self._component(revision_id, name="revision_id"),
            f"{self._component(artifact_id, name='artifact_id')}{normalized_suffix}",
        )

    def provider_path(
        self, application_id: str, operation_id: str, artifact_id: str
    ) -> Path:
        return self._target(
            "provider",
            self._component(application_id, name="application_id"),
            self._component(operation_id, name="operation_id"),
            f"{self._component(artifact_id, name='artifact_id')}.json",
        )

    def manifest_path(self, manifest_id: str) -> Path:
        component = self._component(manifest_id, name="manifest_id")
        self._require_uuid4(component)
        return self._target("manifests", f"{component}.json")

    @staticmethod
    def _require_uuid4(value: str) -> None:
        try:
            parsed = uuid.UUID(value)
        except ValueError as exc:
            raise ValueError(f"manifest_id must be a UUIDv4: {value}") from exc
        if parsed.version != 4 or str(parsed) != value:
            raise ValueError(f"manifest_id must be a UUIDv4: {value}")

    def _approved_destination(self, candidate: Path | str) -> Path:
        unresolved = Path(candidate)
        if ".." in unresolved.parts:
            raise ValueError(f"payload destination contains traversal: {candidate}")
        if unresolved.is_absolute():
            relative = relative_within(self._artifacts_root, unresolved)
        else:
            relative = unresolved

        parts = relative.parts
        manifest_id = Path(parts[1]).stem if len(parts) == 2 else None
        approved = (
            len(parts) == 3
            and parts[0] == "snapshots"
            and parts[2].endswith(".txt")
            or len(parts) == 4
            and parts[0] == "revisions"
            and parts[3] in {"resume.json", "resume.md"}
            or len(parts) == 4
            and parts[0] == "outputs"
            and Path(parts[3]).suffix in self._OUTPUT_SUFFIXES
            or len(parts) == 4
            and parts[0] == "provider"
            and parts[3].endswith(".json")
            or len(parts) == 2
            and parts[0] == "manifests"
            and parts[1].endswith(".json")
        )
        if not approved:
            raise ValueError(f"payload destination is not an approved layout: {candidate}")
        if manifest_id is not None and parts[0] == "manifests":
            self._require_uuid4(manifest_id)
        return resolve_within(self._artifacts_root, relative)

    def commit(
        self,
        destination: Path | str,
        *,
        write: PayloadWriter,
        validate: PayloadValidator,
    ) -> StoredPayload:
        """Stage, validate, hash, and atomically publish one immutable payload.

        The returned metadata is the registration boundary. The caller registers it
        in SQLite; a failure there deliberately leaves a safe filesystem orphan.
        """
        target = self._approved_destination(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        target = resolve_within(self._artifacts_root, target)
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"immutable payload already exists: {target}")

        temp_directory = resolve_within(self._temp_root, self._TEMP_DIRECTORY)
        temp_directory.mkdir(parents=True, exist_ok=True)
        temporary = resolve_within(
            self._temp_root, temp_directory / f"{uuid.uuid4()}.tmp"
        )

        write(temporary)
        resolved_temporary = resolve_within(self._temp_root, temporary)
        if temporary.is_symlink() or not resolved_temporary.is_file():
            raise ValueError(f"payload writer did not create a regular temp file: {temporary}")
        if validate(resolved_temporary) is False:
            raise ValueError(f"payload validation failed: {temporary}")

        digest = sha256_file(resolved_temporary)
        size = resolved_temporary.stat().st_size

        target = resolve_within(self._artifacts_root, target)
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"immutable payload already exists: {target}")
        os.rename(resolved_temporary, target)

        return StoredPayload(
            path=target,
            workspace_relative=relative_within(
                self._workspace_root, target
            ).as_posix(),
            sha256=digest,
            size=size,
        )

    def commit_snapshot(
        self,
        application_id: str,
        snapshot_id: str,
        text: str,
    ) -> SnapshotPayload:
        stored = self.commit(
            self.snapshot_path(application_id, snapshot_id),
            write=lambda path: path.write_bytes(text.encode("utf-8")),
            validate=lambda path: path.is_file(),
        )
        return SnapshotPayload(
            reference=stored.workspace_relative,
            sha256=stored.sha256,
            size=stored.size,
        )

    def read_snapshot(self, reference: str, expected_hash: str) -> str:
        candidate = resolve_within(self._workspace_root, reference)
        approved = self._approved_destination(candidate)
        relative = relative_within(self._artifacts_root, approved)
        if len(relative.parts) != 3 or relative.parts[0] != "snapshots":
            raise ValueError(f"payload is not a JobSnapshot: {reference}")
        if not approved.is_file():
            raise FileNotFoundError(f"snapshot payload does not exist: {reference}")
        actual_hash = sha256_file(approved)
        if actual_hash != expected_hash:
            raise ValueError(
                f"snapshot payload hash mismatch: expected {expected_hash}, got {actual_hash}"
            )
        return approved.read_bytes().decode("utf-8")

    @staticmethod
    def _reference(stored: StoredPayload) -> SnapshotPayload:
        return SnapshotPayload(
            reference=stored.workspace_relative,
            sha256=stored.sha256,
            size=stored.size,
        )

    @staticmethod
    def _valid_json(path: Path) -> bool:
        json.loads(path.read_text(encoding="utf-8"))
        return True

    def commit_revision(
        self,
        application_id: str,
        revision_id: str,
        structured_json: str,
        markdown: str,
    ) -> RevisionPayloads:
        """Commit and re-hash both immutable ApprovedRevision payloads.

        SQLite registration is deliberately left to the caller. If either
        registration later fails, these files are safe reconciliation orphans.
        """
        structured = self.commit(
            self.revision_path(application_id, revision_id, format="json"),
            write=lambda path: path.write_bytes(structured_json.encode("utf-8")),
            validate=self._valid_json,
        )
        rendered = self.commit(
            self.revision_path(application_id, revision_id, format="md"),
            write=lambda path: path.write_bytes(markdown.encode("utf-8")),
            validate=lambda path: path.is_file(),
        )
        for stored in (structured, rendered):
            actual = sha256_file(stored.path)
            if actual != stored.sha256:
                raise ValueError(
                    "committed revision payload hash mismatch: "
                    f"expected {stored.sha256}, got {actual}"
                )
        return RevisionPayloads(
            structured=self._reference(structured),
            markdown=self._reference(rendered),
        )

    def temp_orphans(self, *, now: float | None = None) -> list[TempOrphan]:
        """Report store-owned temp files for reconciliation without deleting them."""
        observed_at = time.time() if now is None else now
        temp_directory = resolve_within(self._temp_root, self._TEMP_DIRECTORY)
        if not temp_directory.exists():
            return []

        orphans: list[TempOrphan] = []
        for candidate in sorted(temp_directory.iterdir()):
            path = resolve_within(self._temp_root, candidate)
            if candidate.is_symlink() or not path.is_file():
                continue
            stat = path.stat()
            orphans.append(
                TempOrphan(
                    path=path,
                    workspace_relative=relative_within(
                        self._workspace_root, path
                    ).as_posix(),
                    age_seconds=max(0.0, observed_at - stat.st_mtime),
                    size=stat.st_size,
                )
            )
        return orphans
