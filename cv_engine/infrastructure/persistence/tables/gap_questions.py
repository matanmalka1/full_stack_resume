"""Gap questions and what the user did with each: both immutable records.

`gap_questions` is what one `ask_gap_questions` Operation asked about one analysis;
`gap_answers` is the user's one outcome per question - an answer turned into a
pending fact, or a skip. Neither row changes once written (the shared guard
triggers), and both reach their user through their Application.
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

from ._helpers import IsoTimestamp
from ._metadata import metadata

gap_questions = Table(
    "gap_questions",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("application_id", UUID(as_uuid=False), ForeignKey("applications.id"), nullable=False),
    Column("job_analysis_id", UUID(as_uuid=False), nullable=False),
    # The Operation that asked; one question set per Operation.
    Column("operation_id", UUID(as_uuid=False), ForeignKey("operations.id"), nullable=False),
    Column("ordinal", Integer, nullable=False),
    Column("requirement_id", Text, nullable=False),
    # The requirement as the analysis read it, copied so the question reads alone.
    Column("requirement_text", Text, nullable=False),
    Column("importance", Text, nullable=False),
    Column("coverage", Text, nullable=False),
    Column("language", Text, nullable=False),
    Column("question", Text, nullable=False),
    Column("created_at", IsoTimestamp(), nullable=False),
    # The analysis is one of this Application's own.
    ForeignKeyConstraint(
        ["application_id", "job_analysis_id"],
        ["job_analyses.application_id", "job_analyses.id"],
    ),
    CheckConstraint("ordinal > 0", name="ordinal_positive"),
    CheckConstraint("coverage IN ('partial', 'unsupported')", name="coverage"),
    CheckConstraint("importance IN ('mandatory', 'preferred', 'unknown')", name="importance"),
    CheckConstraint("language IN ('en', 'he')", name="language"),
    CheckConstraint("length(trim(question)) > 0", name="question_nonempty"),
    UniqueConstraint("operation_id", "ordinal"),
    UniqueConstraint("application_id", "id"),
)

gap_answers = Table(
    "gap_answers",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("application_id", UUID(as_uuid=False), ForeignKey("applications.id"), nullable=False),
    # One outcome per question, ever.
    Column("gap_question_id", UUID(as_uuid=False), nullable=False, unique=True),
    Column("outcome", Text, nullable=False),
    # The user's answer, verbatim; NULL for a skip.
    Column("answer", Text),
    # The pending fact drafted from the answer, and the Operation that drafted it.
    Column("fact_id", String),
    Column("operation_id", UUID(as_uuid=False), ForeignKey("operations.id")),
    Column("created_at", IsoTimestamp(), nullable=False),
    ForeignKeyConstraint(
        ["application_id", "gap_question_id"],
        ["gap_questions.application_id", "gap_questions.id"],
    ),
    CheckConstraint("outcome IN ('answered', 'skipped')", name="outcome"),
    CheckConstraint(
        "(outcome = 'answered') = "
        "(answer IS NOT NULL AND fact_id IS NOT NULL AND operation_id IS NOT NULL)",
        name="answered_has_fact",
    ),
    CheckConstraint(
        "outcome = 'answered' OR (answer IS NULL AND fact_id IS NULL AND operation_id IS NULL)",
        name="skipped_is_empty",
    ),
)
