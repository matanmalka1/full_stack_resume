from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..application.errors import KnowledgeRejected
from ..application.ports import TaskContract, TaskContracts
from ..domain.analysis.requirements.concepts import (
    RequirementConceptError,
    RequirementConceptStore,
)
from ..domain.candidate import CANDIDATE_FILE, CandidateContextError, build_candidate_context
from ..domain.contracts.knowledge import (
    CandidateContext,
    FactSource,
)
from ..domain.emphasis import EmphasisPolicyError, EmphasisPolicyStore
from ..domain.facts import (
    FACT_SOURCE_NAMES,
    FactStore,
    FactStoreError,
    parse_fact_source,
)
from ..domain.knowledge import Knowledge
from ..domain.presentations import PresentationError, PresentationStore
from ..domain.profiles import ProfileStore, ProfileStoreError
from ..util import sha256_text
from .paths import resolve_within

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
    if not isinstance(prompt, dict) or not isinstance(tasks, dict):
        raise KnowledgeRejected("AI task contracts must declare prompt and tasks")
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
        task_version = entry.get("version")
        # The input and output schema versions default to the task's own version
        # rather than to a literal, so a task that declares one version declares
        # all three consistently and cannot end up with an invented default.
        fields: dict[str, Any] = {
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
            model=entry.get("model"),
            **fields,
        )
    if not declared:
        raise KnowledgeRejected("AI task contracts declare no tasks")
    return TaskContracts(
        prompt_version=prompt_version,
        prompt_hash=sha256_text(prompt_text),
        prompt_text=prompt_text,
        tasks=declared,
    )


def read_fact_source(path: Path) -> FactSource:
    """One canonical fact source, parsed from its file."""
    return parse_fact_source(path.read_text(encoding="utf-8"), origin=str(path))


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
        raise EmphasisPolicyError(f"missing emphasis policy: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EmphasisPolicyError(f"invalid emphasis policy {path}: {exc}") from exc
    return EmphasisPolicyStore.from_payload(payload, origin=str(path))


def load_requirement_concepts(knowledge_root: Path) -> RequirementConceptStore:
    path = knowledge_root / "config" / "requirements.json"
    if not path.is_file():
        raise RequirementConceptError(f"missing requirement concepts: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RequirementConceptError(f"invalid requirement concepts {path}: {exc}") from exc
    return RequirementConceptStore.from_payload(payload, origin=str(path))


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


class FileKnowledge:
    """Knowledge in the installation's file layout: `import-knowledge`'s input.

    This is the only place that knows that layout. The application reads Knowledge
    from the user's rows (`DatabaseKnowledge`); the files here are what an import
    reads, and the AI task contracts.
    """

    def __init__(
        self,
        knowledge_root: Path,
        *,
        project_root: Path | None = None,
        temp_root: Path | None = None,
    ):
        self.knowledge_root = Path(knowledge_root).resolve()
        self.project_root = Path(project_root or knowledge_root).resolve()
        self.temp_root = Path(temp_root or (self.project_root / "tmp")).resolve()
        resolve_within(self.project_root, self.knowledge_root)
        resolve_within(self.project_root, self.temp_root)

    @property
    def base_dir(self) -> Path:
        return self.knowledge_root / "base"

    def facts(self) -> FactStore:
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
            requirement_concepts=load_requirement_concepts(self.knowledge_root),
        )
