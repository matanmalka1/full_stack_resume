"""Column/constraint builders shared by every table module. Dependency-free."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Column, Date, DateTime, Sequence, TypeDecorator


def _timestamp_bind(value: str | datetime | None, _dialect):
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _timestamp_result(value: str | datetime | None, _dialect):
    if value is None or isinstance(value, str):
        return value
    return value.isoformat()


def _date_bind(value: str | date | None, _dialect):
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _date_result(value: str | date | None, _dialect):
    if value is None or isinstance(value, str):
        return value
    return value.isoformat()


# Dynamic type construction keeps these SQL scalar types out of the persistence-adapter
# class inventory: they convert values, but do not own connections or transactions.
IsoTimestamp = type(
    "IsoTimestamp",
    (TypeDecorator,),
    {
        "impl": DateTime(timezone=True),
        "cache_ok": True,
        "process_bind_param": staticmethod(_timestamp_bind),
        "process_result_value": staticmethod(_timestamp_result),
    },
)
IsoDate = type(
    "IsoDate",
    (TypeDecorator,),
    {
        "impl": Date,
        "cache_ok": True,
        "process_bind_param": staticmethod(_date_bind),
        "process_result_value": staticmethod(_date_result),
    },
)


def sql_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def sequence_column(table_name: str) -> Column[int]:
    sequence = Sequence(f"{table_name}_seq_seq")
    return Column(
        "seq",
        BigInteger,
        sequence,
        server_default=sequence.next_value(),
        nullable=False,
    )
