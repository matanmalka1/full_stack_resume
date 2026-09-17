from __future__ import annotations

import pytest
from sqlalchemy import func, insert, select

from cv_engine.application.transactions import (
    active_transaction_for_tests,
    assert_external_io_allowed,
)
from cv_engine.infrastructure.payloads import PayloadStore
from cv_engine.infrastructure.persistence import SqlAlchemyTransactionManager
from cv_engine.infrastructure.persistence.tables import applications


def _application(application_id: str) -> dict[str, str]:
    return {
        "id": application_id,
        "company": "Transaction Co",
        "target_role": "Engineer",
        "current_status": "saved",
        "notes": "",
        "source": "manual",
        "created_at": "2026-09-17T00:00:00+00:00",
        "updated_at": "2026-09-17T00:00:00+00:00",
    }


def test_write_scope_commits_on_success_and_closes_token(database_engine) -> None:
    transactions = SqlAlchemyTransactionManager(database_engine)

    with transactions.write() as tx:
        connection = transactions.connection_for(tx, access="write")
        connection.execute(insert(applications).values(**_application("committed")))
        assert tx.active

    assert not tx.active
    assert active_transaction_for_tests() is None
    with database_engine.connect() as connection:
        count = connection.execute(
            select(func.count()).select_from(applications).where(applications.c.id == "committed")
        ).scalar_one()
    assert count == 1


def test_write_scope_rolls_back_on_exception(database_engine) -> None:
    transactions = SqlAlchemyTransactionManager(database_engine)

    with pytest.raises(RuntimeError, match="stop"):
        with transactions.write() as tx:
            transactions.connection_for(tx, access="write").execute(
                insert(applications).values(**_application("rolled-back"))
            )
            raise RuntimeError("stop")

    assert not tx.active
    assert active_transaction_for_tests() is None
    with database_engine.connect() as connection:
        count = connection.execute(
            select(func.count()).select_from(applications).where(applications.c.id == "rolled-back")
        ).scalar_one()
    assert count == 0


def test_read_scope_rolls_back_and_cannot_write_through_repository_access(database_engine) -> None:
    transactions = SqlAlchemyTransactionManager(database_engine)

    with transactions.read() as tx:
        transactions.connection_for(tx).execute(select(1)).scalar_one()
        with pytest.raises(TypeError, match="write transaction"):
            transactions.connection_for(tx, access="write")


def test_closed_and_foreign_transactions_are_rejected(database_engine) -> None:
    owner = SqlAlchemyTransactionManager(database_engine)
    foreign = SqlAlchemyTransactionManager(database_engine)

    with owner.read() as tx:
        with pytest.raises(TypeError, match="another transaction manager"):
            foreign.connection_for(tx)

    with pytest.raises(RuntimeError, match="closed"):
        owner.connection_for(tx)


def test_nested_transactions_are_forbidden_across_managers(database_engine) -> None:
    first = SqlAlchemyTransactionManager(database_engine)
    second = SqlAlchemyTransactionManager(database_engine)

    with first.read():
        with pytest.raises(RuntimeError, match="nested database transactions"):
            with second.write():
                pass

    assert active_transaction_for_tests() is None


def test_transaction_scope_cannot_be_reused(database_engine) -> None:
    transactions = SqlAlchemyTransactionManager(database_engine)
    scope = transactions.read()

    with scope:
        pass
    with pytest.raises(RuntimeError, match="cannot be reused"):
        with scope:
            pass


def test_payload_store_refuses_writes_inside_transaction(database_engine, app_paths) -> None:
    transactions = SqlAlchemyTransactionManager(database_engine)
    payloads = PayloadStore(app_paths)

    with transactions.write():
        with pytest.raises(RuntimeError, match="immutable payload write"):
            payloads.commit_snapshot("application", "snapshot", "job text")

    assert not payloads.snapshot_path("application", "snapshot").exists()
    with transactions.read():
        with pytest.raises(RuntimeError, match="object-store write"):
            assert_external_io_allowed("object-store write")
    assert_external_io_allowed("object-store write")
