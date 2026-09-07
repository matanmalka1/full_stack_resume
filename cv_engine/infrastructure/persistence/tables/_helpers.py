"""Column/constraint builders shared by every table module. Dependency-free."""

from __future__ import annotations

from sqlalchemy import BigInteger, Column, Sequence


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
