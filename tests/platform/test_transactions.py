from __future__ import annotations

import pytest
from sqlalchemy import func, insert, select

from cv_engine.application.ports import AnalysisContext
from cv_engine.application.transactions import (
    active_transaction_for_tests,
    assert_external_io_allowed,
)
from cv_engine.infrastructure.knowledge import FileKnowledge
from cv_engine.infrastructure.payloads import PayloadStore
from cv_engine.infrastructure.persistence import SqlAlchemyTransactionManager
from cv_engine.infrastructure.persistence.tables import applications
from cv_engine.infrastructure.providers import OpenAIResponsesProvider
from cv_engine.util import new_id


def _application(application_id: str) -> dict[str, str]:
    return {
        "id": application_id,
        "company": "Transaction Co",
        "target_role": "Engineer",
        "current_status": "saved",
        "notes": "",
        "created_at": "2026-09-17T00:00:00+00:00",
        "updated_at": "2026-09-17T00:00:00+00:00",
    }


def test_write_scope_commits_once_rolls_back_on_exception_and_closes(database_engine) -> None:
    transactions = SqlAlchemyTransactionManager(database_engine)

    committed_id = new_id()
    rolled_back_id = new_id()
    with transactions.write() as committed:
        connection = transactions.connection_for(committed, access="write")
        connection.execute(insert(applications).values(**_application(committed_id)))
        assert committed.active

    assert not committed.active
    assert active_transaction_for_tests() is None

    with pytest.raises(RuntimeError, match="stop"):
        with transactions.write() as rolled_back:
            transactions.connection_for(rolled_back, access="write").execute(
                insert(applications).values(**_application(rolled_back_id))
            )
            raise RuntimeError("stop")

    assert not rolled_back.active
    assert active_transaction_for_tests() is None
    with database_engine.connect() as connection:
        counts = {
            application_id: connection.execute(
                select(func.count())
                .select_from(applications)
                .where(applications.c.id == application_id)
            ).scalar_one()
            for application_id in (committed_id, rolled_back_id)
        }
    assert counts == {committed_id: 1, rolled_back_id: 0}


def test_read_closed_and_foreign_tokens_are_rejected(database_engine) -> None:
    owner = SqlAlchemyTransactionManager(database_engine)
    foreign = SqlAlchemyTransactionManager(database_engine)

    with owner.read() as tx:
        owner.connection_for(tx).execute(select(1)).scalar_one()
        with pytest.raises(TypeError, match="write transaction"):
            owner.connection_for(tx, access="write")
        with pytest.raises(TypeError, match="another transaction manager"):
            foreign.connection_for(tx)

    with pytest.raises(RuntimeError, match="closed"):
        owner.connection_for(tx)


def test_scopes_cannot_nest_across_managers_or_be_reused(database_engine) -> None:
    first = SqlAlchemyTransactionManager(database_engine)
    second = SqlAlchemyTransactionManager(database_engine)

    with first.read():
        with pytest.raises(RuntimeError, match="nested database transactions"):
            with second.write():
                pass

    assert active_transaction_for_tests() is None

    scope = first.read()
    with scope:
        pass
    with pytest.raises(RuntimeError, match="cannot be reused"):
        with scope:
            pass


def _knowledge_payload() -> dict:
    return {
        "fact_id": "transaction.guard",
        "meaning": "Knowledge writes are kept outside database transactions.",
        "renderings": {"en": "Knowledge writes are kept outside database transactions."},
        "tags": ["architecture"],
        "provenance": "transaction boundary regression test",
        "resume_style": "bullet",
    }


def _payloads_refuse(transactions, scope, app_paths, **_fixtures) -> None:
    payloads = PayloadStore(app_paths)
    with getattr(transactions, scope)():
        with pytest.raises(RuntimeError, match="immutable payload write"):
            payloads.commit_snapshot("application", "snapshot", "job text")
        with pytest.raises(RuntimeError, match="payload inventory is forbidden"):
            payloads.payload_inventory()
        with pytest.raises(RuntimeError, match="object-store write"):
            assert_external_io_allowed("object-store write")
    assert not payloads.snapshot_path("application", "snapshot").exists()
    assert_external_io_allowed("object-store write")


def _knowledge_refuses(transactions, scope, app_paths, **_fixtures) -> None:
    knowledge = FileKnowledge(
        app_paths.knowledge_root,
        project_root=app_paths.root,
        temp_root=app_paths.temp_root,
    )
    staged, _fact = knowledge.stage_create_fact(
        "guarded-mutation", "situational_skills.json", _knowledge_payload()
    )
    before = knowledge.staged_file_state(staged)
    with getattr(transactions, scope)():
        with pytest.raises(RuntimeError, match="Knowledge"):
            knowledge.stage_create_fact(
                "refused-mutation", "situational_skills.json", _knowledge_payload()
            )
        with pytest.raises(RuntimeError, match="Knowledge"):
            knowledge.activate_staged(staged)
        with pytest.raises(RuntimeError, match="Knowledge"):
            knowledge.restore_staged(staged)
        with pytest.raises(RuntimeError, match="Knowledge"):
            knowledge.discard_staged(staged)
    assert not (app_paths.temp_root / "knowledge" / "refused-mutation").exists()
    assert knowledge.staged_file_state(staged) == before


def _provider_refuses(transactions, scope, task_contracts, fake_openai, **_fixtures) -> None:
    provider = fake_openai.provider(task_contracts)
    transport = OpenAIResponsesProvider(model="gpt-5.6-terra", api_key="test-key")
    with getattr(transactions, scope)():
        with pytest.raises(RuntimeError, match="provider execution"):
            provider.propose_analysis(
                AnalysisContext(job_text="job", candidate_facts=[], overrides={})
            )
        with pytest.raises(RuntimeError, match="provider HTTP request"):
            transport._post({})
    assert fake_openai.calls == []


@pytest.mark.parametrize("scope", ["read", "write"])
@pytest.mark.parametrize(
    "boundary",
    [_payloads_refuse, _knowledge_refuses, _provider_refuses],
    ids=["payloads", "knowledge", "provider"],
)
def test_outbound_io_is_refused_inside_either_scope(
    database_engine, app_paths, task_contracts, fake_openai, boundary, scope
) -> None:
    boundary(
        SqlAlchemyTransactionManager(database_engine),
        scope,
        app_paths=app_paths,
        task_contracts=task_contracts,
        fake_openai=fake_openai,
    )
