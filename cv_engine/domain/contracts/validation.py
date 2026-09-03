"""Validation findings and Ready qualification contracts."""

from __future__ import annotations

from typing import Any, Self

from pydantic import Field, model_validator

from .base import StrictModel


class ValidationIssue(StrictModel):
    group: str
    code: str
    message: str
    hard: bool = True


class ValidationReport(StrictModel):
    report_schema_version: str | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    passed: bool
    groups: dict[str, bool]
    issues: list[ValidationIssue] = []
    evidence: dict[str, Any] = {}

    @classmethod
    def from_findings(
        cls,
        groups: dict[str, bool],
        issues: list[ValidationIssue],
        *,
        evidence: dict[str, Any] | None = None,
    ) -> Self:
        """Build a report whose pass result is derived from its findings."""
        return cls(
            report_schema_version="2.0",
            passed=all(groups.values()) and not any(issue.hard for issue in issues),
            groups=groups,
            issues=issues,
            evidence=evidence if evidence is not None else {},
        )

    @model_validator(mode="after")
    def passed_agrees_with_findings(self) -> ValidationReport:
        if not self.passed:
            return self
        failed_groups = sorted(group for group, passed in self.groups.items() if not passed)
        if failed_groups:
            raise ValueError(f"report claims to have passed with failed groups: {failed_groups}")
        hard_issues = sorted({issue.code for issue in self.issues if issue.hard})
        if hard_issues:
            raise ValueError(f"report claims to have passed with hard failures: {hard_issues}")
        return self


class ReadyQualification(StrictModel):
    """Current integrity projection for one immutable approved revision."""

    application_id: str
    approved_revision_id: str
    pdf_artifact_version_id: str | None = None
    html_artifact_version_id: str | None = None
    ready_qualified: bool
    validation: ValidationReport

    @model_validator(mode="after")
    def qualification_agrees_with_evidence(self) -> ReadyQualification:
        if self.ready_qualified != self.validation.passed:
            raise ValueError("ready_qualified must be derived from its validation evidence")
        if self.ready_qualified and self.pdf_artifact_version_id is None:
            raise ValueError("ready_qualified requires an exact PDF artifact version")
        if self.ready_qualified and self.html_artifact_version_id is None:
            raise ValueError("ready_qualified requires an exact HTML artifact version")
        return self
