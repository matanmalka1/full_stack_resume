from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path

from ..application.errors import KnowledgeRejected
from ..application.knowledge_mutations import (
    KnowledgeFileState,
    KnowledgeMutation,
    StagedKnowledgeFile,
)
from ..application.ports import TaskContract, TaskContracts
from ..domain.candidate import CANDIDATE_FILE, CandidateContextError, build_candidate_context
from ..domain.facts import (
    FACT_SOURCE_NAMES,
    FactStore,
    FactStoreError,
    build_new_fact,
    parse_fact_source,
    parse_fact_source_document,
    render_fact_source,
    source_name_of,
    with_new_fact,
    with_promoted_fact,
)
from ..domain.knowledge import Knowledge
from ..domain.models import CandidateContext, Fact, FactSource, FactStatus, Profile
from ..domain.presentations import PresentationError, PresentationStore
from ..domain.profiles import ProfileStore, ProfileStoreError, attach_fact_to_section
from ..domain.selection import EmphasisPolicyStore, SelectionError
from ..util import sha256_file, sha256_text, utc_now
from .paths import relative_within, resolve_within

TASK_CONTRACTS_FILE = Path("ai") / "contracts" / "task_contracts.json"


def load_task_contracts(knowledge_root: Path) -> TaskContracts:
    """Read the declared AI task contracts and the prompt they name.

    The file is Knowledge (architecture §6.3), so it is read here with the
    facts, profiles, and policies rather than by the provider adapter. Missing,
    unparseable, or self-inconsistent is refused rather than defaulted: a task
    that ran under an invented contract version would record provenance nobody
    can trace back to a file.
    """
    path = knowledge_root / TASK_CONTRACTS_FILE
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise KnowledgeRejected(f"AI task contracts are missing: {TASK_CONTRACTS_FILE}") from exc
    except (json.JSONDecodeError, OSError) as exc:
        raise KnowledgeRejected(f"AI task contracts are unreadable: {exc}") from exc
    if not isinstance(document, dict):
        raise KnowledgeRejected("AI task contracts must be an object")
    prompt = document.get("prompt")
    tasks = document.get("tasks")
    version = document.get("version")
    if not isinstance(version, str) or not isinstance(prompt, dict) or not isinstance(tasks, dict):
        raise KnowledgeRejected("AI task contracts must declare version, prompt, and tasks")
    prompt_version = prompt.get("version")
    prompt_file = prompt.get("file")
    if not isinstance(prompt_version, str) or not isinstance(prompt_file, str):
        raise KnowledgeRejected("the AI prompt contract must declare a version and a file")
    prompt_path = resolve_within(knowledge_root, knowledge_root / prompt_file)
    try:
        prompt_text = prompt_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise KnowledgeRejected(f"the declared AI prompt is unreadable: {prompt_file}") from exc
    declared: dict[str, TaskContract] = {}
    for name, entry in tasks.items():
        if not isinstance(entry, dict):
            raise KnowledgeRejected(f"AI task contract {name} must be an object")
        task_version = entry.get("version", version)
        # The input and output schema versions default to the task's own version
        # rather than to a literal, so a task that declares one version declares
        # all three consistently and cannot end up with an invented default.
        fields = {
            "input": entry.get("input"),
            "input_schema_version": entry.get("input_schema_version", task_version),
            "output": entry.get("output"),
            "output_schema_version": entry.get("output_schema_version", task_version),
        }
        missing = sorted(key for key, value in fields.items() if not isinstance(value, str))
        if not isinstance(task_version, str) or missing:
            raise KnowledgeRejected(
                f"AI task contract {name} must declare a version, input, and output: "
                f"missing {', '.join(missing) or 'version'}"
            )
        declared[name] = TaskContract(
            name=name,
            version=task_version,
            critical_state=bool(entry.get("critical_state", True)),
            model=entry.get("model"),
            **fields,
        )
    if not declared:
        raise KnowledgeRejected("AI task contracts declare no tasks")
    return TaskContracts(
        version=version,
        prompt_version=prompt_version,
        prompt_hash=sha256_text(prompt_text),
        prompt_text=prompt_text,
        tasks=declared,
    )


def read_fact_source(path: Path) -> FactSource:
    """One canonical fact source, parsed from its file."""
    return parse_fact_source(path.read_text(encoding="utf-8"), origin=str(path))


def _write_fact_source(path: Path, title: str, source: FactSource) -> None:
    path.write_text(render_fact_source(title, source), encoding="utf-8")


def load_fact_store(base_dir: Path) -> FactStore:
    missing = [name for name in FACT_SOURCE_NAMES if not (base_dir / name).is_file()]
    if missing:
        raise FactStoreError(f"missing canonical fact sources: {', '.join(missing)}")
    return FactStore.from_sources(
        {name: read_fact_source(base_dir / name) for name in FACT_SOURCE_NAMES}
    )


def load_profile_store(knowledge_root: Path, facts: FactStore) -> ProfileStore:
    documents: dict[str, dict] = {}
    for path in sorted((knowledge_root / "profiles").glob("**/*.yaml")):
        try:
            documents[str(path)] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ProfileStoreError(f"invalid profile {path}: {exc}") from exc
    return ProfileStore.from_documents(documents, facts)


def load_emphasis_policies(knowledge_root: Path) -> EmphasisPolicyStore:
    path = knowledge_root / "config" / "emphasis.json"
    if not path.is_file():
        raise SelectionError(f"missing emphasis policy: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SelectionError(f"invalid emphasis policy {path}: {exc}") from exc
    return EmphasisPolicyStore.from_payload(payload, origin=str(path))


def load_presentations(knowledge_root: Path, facts: FactStore) -> PresentationStore:
    path = knowledge_root / "rendering" / "rules" / "presentations.json"
    if not path.is_file():
        raise PresentationError(f"missing presentation rules: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PresentationError(f"invalid presentation rules {path}: {exc}") from exc
    return PresentationStore.from_payload(payload, facts, origin=str(path))


def load_candidate_context(knowledge_root: Path, facts: FactStore) -> CandidateContext:
    path = knowledge_root / "base" / CANDIDATE_FILE
    if not path.is_file():
        raise CandidateContextError(f"no candidate context in this project: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CandidateContextError(f"invalid candidate context {path}: {exc}") from exc
    return build_candidate_context(payload, facts, origin=str(path))


def seed_fact_before_project(
    base_dir: Path, source_name: str, payload: dict, *, canonical: bool = False
) -> Fact:
    """Seed bootstrap Knowledge before its journal exists.

    Normal commands must use ``KnowledgeService``. This helper exists only for
    constructing an isolated test Knowledge fixture before services
    and database are created.
    """
    store = load_fact_store(base_dir)
    record = build_new_fact(store, source_name, payload, canonical=canonical)
    path = base_dir / source_name
    title, source = parse_fact_source_document(path.read_text(encoding="utf-8"), origin=str(path))
    _write_fact_source(path, title, with_new_fact(source, record, canonical=canonical))
    return record.model_copy(update={"source_file": f"base/{source_name}"})


class FileKnowledge:
    """Knowledge as it is actually stored: version-controlled files.

    This is the only place that knows the knowledge layout inside the project.
    Every command re-reads through it rather than holding a long-lived cache,
    so a manual edit between commands is seen rather than assumed away.
    """

    def __init__(
        self,
        knowledge_root: Path,
        *,
        project_root: Path | None = None,
        temp_root: Path | None = None,
        has_prepared_mutation: Callable[[], bool] | None = None,
    ):
        self.knowledge_root = Path(knowledge_root).resolve()
        self.project_root = Path(project_root or knowledge_root).resolve()
        self.temp_root = Path(temp_root or (self.project_root / "tmp")).resolve()
        self._has_prepared_mutation = has_prepared_mutation
        resolve_within(self.project_root, self.knowledge_root)
        resolve_within(self.project_root, self.temp_root)

    @property
    def base_dir(self) -> Path:
        return self.knowledge_root / "base"

    def facts(self) -> FactStore:
        if self._has_prepared_mutation is not None and self._has_prepared_mutation():
            raise FactStoreError("Knowledge has an uncommitted prepared mutation")
        return load_fact_store(self.base_dir)

    def task_contracts(self) -> TaskContracts:
        return load_task_contracts(self.knowledge_root)

    def load(self) -> Knowledge:
        facts = self.facts()
        return Knowledge(
            facts=facts,
            profiles=load_profile_store(self.knowledge_root, facts),
            policies=load_emphasis_policies(self.knowledge_root),
            candidate=load_candidate_context(self.knowledge_root, facts),
            presentations=load_presentations(self.knowledge_root, facts),
        )

    def _validate_overrides(self, overrides: dict[Path, str]) -> Knowledge:
        """Load the complete Knowledge graph with proposed documents substituted."""
        normalized = {path.resolve(): text for path, text in overrides.items()}
        fact_sources: dict[str, FactSource] = {}
        for name in FACT_SOURCE_NAMES:
            path = self.base_dir / name
            text = (
                normalized[path.resolve()]
                if path.resolve() in normalized
                else path.read_text("utf-8")
            )
            fact_sources[name] = parse_fact_source(text, origin=str(path))
        facts = FactStore.from_sources(fact_sources)

        documents: dict[str, dict] = {}
        for path in sorted((self.knowledge_root / "profiles").glob("**/*.yaml")):
            text = (
                normalized[path.resolve()]
                if path.resolve() in normalized
                else path.read_text("utf-8")
            )
            documents[str(path)] = json.loads(text)
        return Knowledge(
            facts=facts,
            profiles=ProfileStore.from_documents(documents, facts),
            policies=load_emphasis_policies(self.knowledge_root),
            candidate=load_candidate_context(self.knowledge_root, facts),
            presentations=load_presentations(self.knowledge_root, facts),
        )

    def _stage_validated(
        self,
        mutation_id: str,
        source: Path,
        proposed_text: str,
        proposed_versions: dict[str, str],
    ) -> StagedKnowledgeFile:
        if not mutation_id or "/" in mutation_id or "\\" in mutation_id:
            raise ValueError("knowledge mutation ID is not a safe path component")
        source = resolve_within(self.knowledge_root, source)
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"knowledge source is not a regular file: {source}")

        stage_dir = resolve_within(self.temp_root, self.temp_root / "knowledge" / mutation_id)
        stage_dir.mkdir(parents=True, exist_ok=False)
        old_path = resolve_within(stage_dir, stage_dir / "old")
        new_path = resolve_within(stage_dir, stage_dir / "new")
        old_bytes = source.read_bytes()
        new_bytes = proposed_text.encode("utf-8")
        try:
            self._write_durable(old_path, old_bytes)
            self._write_durable(new_path, new_bytes)
            self._fsync_directory(stage_dir)
        except Exception:
            for path in (new_path, old_path):
                path.unlink(missing_ok=True)
            stage_dir.rmdir()
            raise
        return StagedKnowledgeFile(
            mutation_id=mutation_id,
            source_reference=relative_within(self.project_root, source).as_posix(),
            staged_reference=relative_within(self.project_root, new_path).as_posix(),
            old_sha256=sha256_file(old_path),
            new_sha256=sha256_file(new_path),
            proposed_versions=proposed_versions,
        )

    def _stage(self, mutation_id: str, source: Path, proposed_text: str) -> StagedKnowledgeFile:
        overrides = {source: proposed_text}
        profile_paths = list((self.knowledge_root / "profiles").glob("**/*.yaml"))
        if profile_paths:
            versions = self._validate_overrides(overrides).versions()
        else:
            fact_sources = {
                name: parse_fact_source(
                    (
                        proposed_text
                        if (self.base_dir / name).resolve() == source.resolve()
                        else (self.base_dir / name).read_text("utf-8")
                    ),
                    origin=str(self.base_dir / name),
                )
                for name in FACT_SOURCE_NAMES
            }
            facts = FactStore.from_sources(fact_sources)
            versions = {
                "facts": facts.version,
                "facts_lifecycle": facts.lifecycle_version,
            }
        return self._stage_validated(mutation_id, source, proposed_text, versions)

    @staticmethod
    def _write_durable(path: Path, content: bytes) -> None:
        with path.open("xb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _paths(self, staged: StagedKnowledgeFile) -> tuple[Path, Path, Path]:
        source = resolve_within(self.project_root, staged.source_reference)
        source = resolve_within(self.knowledge_root, source)
        new_path = resolve_within(self.project_root, staged.staged_reference)
        new_path = resolve_within(self.temp_root, new_path)
        old_path = resolve_within(self.temp_root, new_path.with_name("old"))
        if new_path.parent.name != staged.mutation_id or new_path.name != "new":
            raise ValueError("staged Knowledge reference does not match its mutation")
        return source, new_path, old_path

    def stage_create_fact(
        self,
        mutation_id: str,
        source_name: str,
        payload: dict,
        *,
        canonical: bool = False,
    ) -> tuple[StagedKnowledgeFile, Fact]:
        store = self.facts()
        record = build_new_fact(store, source_name, payload, canonical=canonical)
        path = resolve_within(self.base_dir, self.base_dir / source_name)
        title, source = parse_fact_source_document(path.read_text("utf-8"), origin=str(path))
        proposed = render_fact_source(title, with_new_fact(source, record, canonical=canonical))
        staged = self._stage(mutation_id, path, proposed)
        return staged, record.model_copy(update={"source_file": f"base/{source_name}"})

    def stage_promote_fact(
        self,
        mutation_id: str,
        fact_id: str,
        target: FactStatus | str,
        *,
        explicitly_confirmed: bool,
    ) -> tuple[StagedKnowledgeFile, Fact, Fact]:
        status = FactStatus(target)
        store = self.facts()
        before = store.get(fact_id)
        promoted = store.promote(fact_id, status, explicitly_confirmed=explicitly_confirmed)
        path = resolve_within(self.base_dir, self.base_dir / source_name_of(before))
        title, source = parse_fact_source_document(path.read_text("utf-8"), origin=str(path))
        confirmed_at = before.confirmed_at or utc_now()[:10]
        proposed = render_fact_source(
            title, with_promoted_fact(source, fact_id, status, confirmed_at)
        )
        staged = self._stage(mutation_id, path, proposed)
        return staged, before, promoted.model_copy(update={"confirmed_at": confirmed_at})

    def stage_attach_fact(
        self,
        mutation_id: str,
        profile: str,
        fact_id: str,
        section: str,
        *,
        pin: bool = False,
    ) -> tuple[StagedKnowledgeFile, Profile, str]:
        facts = self.facts()
        facts.get(fact_id, canonical_only=True)
        source = load_profile_store(self.knowledge_root, facts).source(profile)
        path = resolve_within(self.knowledge_root, source)
        payload = json.loads(path.read_text("utf-8"))
        updated, document = attach_fact_to_section(
            payload, fact_id, section, origin=path.name, pin=pin
        )
        proposed = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
        staged = self._stage(mutation_id, path, proposed)
        return staged, updated, relative_within(self.project_root, path).as_posix()

    def stage_confirm_and_use_fact(
        self,
        mutation_id: str,
        fact_id: str,
        profile: str,
        section: str,
    ) -> tuple[list[StagedKnowledgeFile], Fact, Fact, Fact, Profile, str, Knowledge]:
        store = self.facts()
        before = store.get(fact_id)
        confirmed = store.promote(
            fact_id, FactStatus.CONFIRMED, explicitly_confirmed=True
        ).model_copy(update={"confirmed_at": before.confirmed_at or utc_now()[:10]})
        canonical = store.promote(
            fact_id, FactStatus.CANONICAL, explicitly_confirmed=True
        ).model_copy(update={"confirmed_at": confirmed.confirmed_at})

        fact_path = resolve_within(self.base_dir, self.base_dir / source_name_of(before))
        title, fact_source = parse_fact_source_document(
            fact_path.read_text("utf-8"), origin=str(fact_path)
        )
        fact_text = render_fact_source(
            title,
            with_promoted_fact(
                fact_source, fact_id, FactStatus.CANONICAL, canonical.confirmed_at or utc_now()[:10]
            ),
        )

        profile_source = load_profile_store(self.knowledge_root, store).source(profile)
        profile_path = resolve_within(self.knowledge_root, profile_source)
        profile_payload = json.loads(profile_path.read_text("utf-8"))
        updated, profile_document = attach_fact_to_section(
            profile_payload, fact_id, section, origin=profile_path.name, pin=True
        )
        profile_text = json.dumps(profile_document, ensure_ascii=False, indent=2) + "\n"
        proposed = self._validate_overrides({fact_path: fact_text, profile_path: profile_text})
        primary = self._stage_validated(mutation_id, fact_path, fact_text, proposed.versions())
        try:
            attachment = self._stage_validated(
                f"{mutation_id}-profile", profile_path, profile_text, proposed.versions()
            )
        except Exception:
            self.discard_staged(primary)
            raise
        return (
            [primary, attachment],
            before,
            confirmed,
            canonical,
            updated,
            relative_within(self.project_root, profile_path).as_posix(),
            proposed,
        )

    def activate_staged(self, staged: StagedKnowledgeFile) -> None:
        source, new_path, old_path = self._paths(staged)
        if sha256_file(source) != staged.old_sha256:
            raise ValueError("Knowledge source changed before activation")
        if sha256_file(old_path) != staged.old_sha256:
            raise ValueError("staged Knowledge backup hash mismatch")
        if sha256_file(new_path) != staged.new_sha256:
            raise ValueError("staged Knowledge file hash mismatch")
        os.replace(new_path, source)
        self._fsync_directory(source.parent)

    def restore_staged(self, staged: StagedKnowledgeFile) -> None:
        source, _new_path, old_path = self._paths(staged)
        if sha256_file(source) != staged.new_sha256:
            raise ValueError("Knowledge source is not the activated mutation")
        if sha256_file(old_path) != staged.old_sha256:
            raise ValueError("staged Knowledge backup hash mismatch")
        os.replace(old_path, source)
        self._fsync_directory(source.parent)

    def discard_staged(self, staged: StagedKnowledgeFile) -> None:
        _source, new_path, old_path = self._paths(staged)
        new_path.unlink(missing_ok=True)
        old_path.unlink(missing_ok=True)
        new_path.parent.rmdir()

    def staged_from_mutation(self, mutation: KnowledgeMutation) -> StagedKnowledgeFile:
        return StagedKnowledgeFile(
            mutation_id=mutation.id,
            source_reference=mutation.source_reference,
            staged_reference=mutation.staged_reference,
            old_sha256=mutation.old_sha256,
            new_sha256=mutation.new_sha256,
            proposed_versions={},
        )

    def staged_file_state(self, staged: StagedKnowledgeFile) -> KnowledgeFileState:
        source, new_path, old_path = self._paths(staged)

        def digest(path: Path) -> str | None:
            return sha256_file(path) if path.is_file() and not path.is_symlink() else None

        return KnowledgeFileState(
            current_sha256=digest(source),
            staged_sha256=digest(new_path),
            backup_sha256=digest(old_path),
        )
