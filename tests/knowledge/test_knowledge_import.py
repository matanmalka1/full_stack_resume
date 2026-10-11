"""`import-knowledge`: file Knowledge into one user's rows (architecture §18.2, §18.7).

The import proves itself: it reads its rows back and refuses to commit anything that
does not rebuild every fact, Profile, and the candidate context it read. These tests
run it over the installation's own Knowledge and over the test project's, and check
the refusals and the database guards around it.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from fixtures.knowledge import SOURCE_ROOT
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import DBAPIError

from cv_engine.admin.cli import main as admin
from cv_engine.application.errors import KnowledgeRejected, StateConflict, UnknownRecord
from cv_engine.application.services.knowledge.importing import KnowledgeImportService
from cv_engine.domain.knowledge_import import join_profile, split_profile
from cv_engine.infrastructure.database_knowledge import DatabaseKnowledge
from cv_engine.infrastructure.knowledge import FileKnowledge
from cv_engine.infrastructure.persistence.accounts import SqlAlchemyAccountRepository
from cv_engine.infrastructure.persistence.tables import (
    candidate_contexts,
    facts,
    profile_bindings,
)
from cv_engine.infrastructure.persistence.user_knowledge import (
    SqlAlchemyUserKnowledgeRepository,
)
from cv_engine.util import new_id

EMAIL = "candidate@example.com"
PASSWORD = "test password, long enough"
PENDING_FACT = {
    "fact_id": "situational.postgres",
    "meaning": "Used PostgreSQL for local application state in a personal project.",
    "renderings": {"en": "Used PostgreSQL for local application state in a personal project."},
    "tags": ["development", "situational", "databases"],
    "provenance": "candidate wording from the user; not yet verified",
    "resume_style": "bullet",
}


@pytest.fixture
def services(bare_services):
    """These tests make the user themselves: services with no user and no Knowledge."""
    return bare_services


@pytest.fixture
def user(services):
    return services.accounts.create_user(EMAIL, PASSWORD)


def _counts(database_engine) -> tuple[int, int, int]:
    with database_engine.connect() as connection:
        return tuple(
            connection.execute(select(func.count()).select_from(table)).scalar_one()
            for table in (facts, candidate_contexts, profile_bindings)
        )


def test_imported_knowledge_reads_back_through_the_installations_templates(
    services, user, project_root, transaction_manager
) -> None:
    """The real Knowledge, as it was before its bindings left `profiles/`.

    The project root holds the installation's facts and its full Profiles (the seed's
    copies, bindings included). Imported, then read back through `DatabaseKnowledge`
    against the installation's own template-only `profiles/`, it is the Knowledge the
    files held: every fact in order, every Profile, and the candidate context. Only the
    fact-store versions move, because per-file source versions are gone (§18.2).
    """
    knowledge = FileKnowledge(project_root).load()

    result = services.knowledge_import.import_knowledge(EMAIL, FileKnowledge(project_root))
    stored = DatabaseKnowledge(
        transaction_manager, SqlAlchemyUserKnowledgeRepository(transaction_manager), SOURCE_ROOT
    ).load(user.id)

    assert result.facts == len(knowledge.facts.facts)
    assert result.profiles == len(knowledge.profiles.profiles)
    assert list(stored.facts.facts.items()) == list(knowledge.facts.facts.items())
    assert stored.profiles.profiles == knowledge.profiles.profiles
    assert stored.profiles.sources == {
        name: Path(source).relative_to(project_root).as_posix()
        for name, source in knowledge.profiles.sources.items()
    }
    assert stored.candidate == knowledge.candidate
    fact_versions = {"facts", "facts_lifecycle"}
    assert {
        name: version for name, version in stored.versions().items() if name not in fact_versions
    } == {
        name: version for name, version in knowledge.versions().items() if name not in fact_versions
    }


def test_rows_carry_each_fact_its_source_order_and_the_split_profiles(
    services, user, project_root, database_engine
) -> None:
    knowledge = FileKnowledge(project_root).load()

    services.knowledge_import.import_knowledge(EMAIL, FileKnowledge(project_root))

    with database_engine.connect() as connection:
        rows = (
            connection.execute(select(facts).order_by(facts.c.source, facts.c.ordinal))
            .mappings()
            .all()
        )
        candidate = connection.execute(select(candidate_contexts)).mappings().one()
        bindings = {
            row["profile_id"]: row
            for row in connection.execute(select(profile_bindings)).mappings()
        }
    assert {row["user_id"] for row in rows} == {user.id}
    for row in rows:
        fact = knowledge.facts.facts[row["fact_id"]]
        assert fact.source_file == f"base/{row['source']}.json"
        assert (row["meaning"], row["renderings"], row["provenance"], row["confirmed_at"]) == (
            fact.meaning,
            fact.renderings,
            fact.provenance,
            fact.confirmed_at,
        )
    for source in {row["source"] for row in rows}:
        ordinals = [row["ordinal"] for row in rows if row["source"] == source]
        assert ordinals == list(range(1, len(ordinals) + 1))
    assert candidate["name_fact_id"] == knowledge.candidate.name_fact_id
    assert candidate["fact_store_version"] == 0
    for profile in knowledge.profiles.profiles.values():
        template, binding = split_profile(profile)
        assert "fact_ids" not in str(template["sections"])
        assert bindings[profile.profile_id]["binding"] == binding
        assert bindings[profile.profile_id]["binding_version"] == 1
        assert join_profile(template, binding) == profile


def test_import_runs_once_and_only_for_a_known_user(
    services, user, project_root, database_engine
) -> None:
    services.knowledge_import.import_knowledge(EMAIL, FileKnowledge(project_root))
    before = _counts(database_engine)

    with pytest.raises(StateConflict, match="runs once"):
        services.knowledge_import.import_knowledge(EMAIL, FileKnowledge(project_root))
    with pytest.raises(UnknownRecord):
        services.knowledge_import.import_knowledge(
            "nobody@example.com", FileKnowledge(project_root)
        )

    assert _counts(database_engine) == before


class _BlindRepository(SqlAlchemyUserKnowledgeRepository):
    """Sees no Knowledge, as a concurrent import that has not committed yet would."""

    def has_knowledge(self, tx, user_id):  # noqa: ANN001
        return False


def test_a_concurrent_second_import_is_refused_by_the_unique_keys(
    user, project_root, transaction_manager, database_engine
) -> None:
    importer = KnowledgeImportService(
        transaction_manager,
        SqlAlchemyAccountRepository(transaction_manager),
        _BlindRepository(transaction_manager),
    )
    importer.import_knowledge(EMAIL, FileKnowledge(project_root))
    before = _counts(database_engine)

    with pytest.raises(StateConflict, match="runs once"):
        importer.import_knowledge(EMAIL, FileKnowledge(project_root))

    assert _counts(database_engine) == before


class _ChangingKnowledge(FileKnowledge):
    """Files edited by someone else between the import's first read and its commit."""

    def __init__(self, root):  # noqa: ANN001
        super().__init__(root)
        self._root = root
        self._loads = 0

    def load(self):  # noqa: ANN201
        self._loads += 1
        if self._loads == 2:
            path = self._root / "base/common.json"
            source = json.loads(path.read_text(encoding="utf-8"))
            source["facts"][0]["meaning"] += " (edited meanwhile)"
            path.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
        return super().load()


def test_files_that_change_during_the_import_commit_nothing(
    services, user, project_root, database_engine
) -> None:
    source = _ChangingKnowledge(project_root)

    with pytest.raises(KnowledgeRejected, match="changed while it was being imported"):
        services.knowledge_import.import_knowledge(EMAIL, source)

    assert _counts(database_engine) == (0, 0, 0)


class _LossyRepository(SqlAlchemyUserKnowledgeRepository):
    """Writes one fact's meaning wrongly, as a broken adapter would."""

    def insert_knowledge(self, tx, user_id, *, facts, **rest):  # noqa: ANN001
        changed = [dict(row) for row in facts]
        changed[0]["meaning"] = changed[0]["meaning"] + " (strengthened)"
        super().insert_knowledge(tx, user_id, facts=changed, **rest)


def test_an_import_that_does_not_rebuild_the_files_commits_nothing(
    user, project_root, transaction_manager, database_engine
) -> None:
    importer = KnowledgeImportService(
        transaction_manager,
        SqlAlchemyAccountRepository(transaction_manager),
        _LossyRepository(transaction_manager),
    )

    with pytest.raises(KnowledgeRejected, match="do not reproduce the files: fact "):
        importer.import_knowledge(EMAIL, FileKnowledge(project_root))

    assert _counts(database_engine) == (0, 0, 0)


def test_a_fact_is_edited_in_place_but_never_changes_identity_or_is_deleted(
    services, user, project_root, database_engine
) -> None:
    """docs/decisions/editable-facts.md: content and status change, identity never does."""
    services.knowledge_import.import_knowledge(EMAIL, FileKnowledge(project_root))
    with database_engine.connect() as connection:
        fact_id = connection.execute(select(facts.c.fact_id).limit(1)).scalar_one()

    with database_engine.begin() as connection:
        connection.execute(
            update(facts)
            .where(facts.c.fact_id == fact_id)
            .values(meaning="a corrected meaning", renderings={"en": "x"}, status="deleted")
        )
    for change in (
        update(facts).where(facts.c.fact_id == fact_id).values(fact_id="renamed.fact"),
        update(facts).where(facts.c.fact_id == fact_id).values(source="user"),
        update(facts).where(facts.c.fact_id == fact_id).values(ordinal=999),
        update(facts).where(facts.c.fact_id == fact_id).values(user_id=new_id()),
        delete(facts).where(facts.c.fact_id == fact_id),
    ):
        with pytest.raises(DBAPIError, match="immutable"):
            with database_engine.begin() as connection:
                connection.execute(change)


def test_cli_imports_from_a_named_directory(services, user, project_root) -> None:
    out, err = io.StringIO(), io.StringIO()

    code = admin(
        ["import-knowledge", "--email", EMAIL, "--from", str(project_root)],
        services=services,
        out=out,
        err=err,
    )

    assert code == 0, err.getvalue()
    assert f"for {EMAIL}" in out.getvalue()
    code = admin(
        ["import-knowledge", "--email", EMAIL, "--from", str(project_root)],
        services=services,
        out=io.StringIO(),
        err=(err := io.StringIO()),
    )
    assert code == 1
    assert "runs once" in err.getvalue()
