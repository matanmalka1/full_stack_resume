"""Human-readable provenance for one approved revision."""

from __future__ import annotations

from ....util import sha256_text
from ...commands import DecisionMarkdownExport
from ...errors import (
    # Re-exported: the v1 CLI and test suite catch WorkflowError from here, and
    # it is bound to the taxonomy's base class, so every refusal below is caught.
    StateConflict,
    UnknownRecord,
)
from .common import DraftServiceBase


class DecisionExport(DraftServiceBase):
    """The Markdown export of a decision record, built from the record alone."""

    def export_decision_markdown(
        self, application_id: str, approved_revision_id: str
    ) -> DecisionMarkdownExport:
        """Render human-readable provenance for one explicitly named revision."""
        try:
            application = self.repo.get_application(application_id)
            revision = self.repo.approved_revision(approved_revision_id)
            decision = self.repo.decision_for_revision(approved_revision_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown decision export source: {exc.args[0]}") from exc
        if (
            revision.application_id != application_id
            or decision["application_id"] != application_id
        ):
            raise StateConflict("approved revision belongs to another application")
        import json

        structured = json.loads(decision["structured_json"])
        selected = structured.get("selected_fact_ids") or []
        gaps = structured.get("accepted_warnings_or_gaps") or {}
        overrides = structured.get("user_overrides") or {}

        def value(item: object) -> str:
            if isinstance(item, (dict, list)):
                return json.dumps(item, ensure_ascii=False, sort_keys=True)
            return str(item)

        lines = [
            "# CV Decision and Provenance",
            "",
            f"- Application: {application['company']} — {application['target_role']}",
            f"- Application ID: `{application_id}`",
            f"- Approved revision ID: `{revision.id}`",
            f"- Approved at: {revision.approved_at}",
            f"- Decision record ID: `{decision['id']}`",
            "",
            "## Decision",
            "",
            decision["summary"],
            "",
            "## Classification",
            "",
        ]
        for label, key in (
            ("Track", "track"),
            ("Profile", "profile"),
            ("Emphasis", "emphasis"),
            ("Language", "language"),
            ("Fit", "fit"),
        ):
            lines.append(f"- {label}: {value(structured.get(key, ''))}")
        lines.extend(["", "## Selected facts", ""])
        lines.extend(f"- `{fact_id}`" for fact_id in selected)
        if not selected:
            lines.append("- None recorded")
        lines.extend(
            [
                "",
                "## Accepted gaps and overrides",
                "",
                f"- Accepted warnings or gaps: {value(gaps)}",
                f"- User overrides: {value(overrides)}",
                "",
                "## Exact lineage",
                "",
                f"- Job snapshot ID: `{revision.job_snapshot_id}`",
                f"- Job analysis ID: `{revision.job_analysis_id}`",
                f"- Selection plan ID: `{revision.selection_plan_id}`",
                f"- Working draft ID: `{revision.working_draft_id}`",
                f"- Validation run ID: `{revision.validation_run_id}`",
                f"- Draft content SHA-256: `{revision.draft_content_hash}`",
                f"- Knowledge context SHA-256: `{revision.knowledge_context_hash}`",
                f"- Candidate context SHA-256: `{revision.candidate_context_hash}`",
                f"- Resume JSON SHA-256: `{revision.resume_json_hash}`",
                f"- Resume Markdown SHA-256: `{revision.resume_markdown_hash}`",
                "",
                "## Approval actor",
                "",
            ]
        )
        for key in ("actor_type", "client", "installation_id", "command"):
            lines.append(f"- {key}: {revision.decision_provenance.get(key, '')}")
        content = "\n".join(lines) + "\n"
        return DecisionMarkdownExport(
            application_id=application_id,
            approved_revision_id=approved_revision_id,
            filename=f"decision-{approved_revision_id}.md",
            content=content,
            content_hash=sha256_text(content),
        )
