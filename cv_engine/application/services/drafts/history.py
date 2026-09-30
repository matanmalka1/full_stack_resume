"""§16 `export_decision_markdown`: human-readable provenance of the current document.

There is no revision history (§20): the history of what was sent is the list of
Submissions. This export describes the document as it stands - its analysis, the
facts its content uses, and its stored content report - and writes nothing.
"""

from __future__ import annotations

import json

from ....domain.analysis.projection import fit_level
from ....domain.document import content_check, dependent_fact_ids, preparation_state
from ....util import sha256_text
from ...commands import DecisionMarkdownExport
from ...errors import UnknownRecord
from ...ports import TransactionManager
from ...ports.analysis_plans import AnalysisContextSourceReader, AnalysisKnowledgeSource
from ...ports.documents import DocumentStore
from ...ports.drafts import DraftHistoryApplicationReader
from ..documents import current_basis, load_knowledge, read_document_source


class DraftHistoryService:
    def __init__(
        self,
        *,
        transactions: TransactionManager,
        documents: DocumentStore,
        sources: AnalysisContextSourceReader,
        applications: DraftHistoryApplicationReader,
        knowledge: AnalysisKnowledgeSource,
    ):
        self.transactions = transactions
        self.documents = documents
        self.sources = sources
        self.applications = applications
        self.knowledge = knowledge

    def export_decision_markdown(self, application_id: str) -> DecisionMarkdownExport:
        """Render the document's provenance. Exempt from the deleted-Application refusal."""
        try:
            with self.transactions.read() as tx:
                application = self.applications.history_application(tx, application_id)
                source = read_document_source(tx, self.documents, self.sources, application_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown decision export source: {exc.args[0]}") from exc
        knowledge = load_knowledge(self.knowledge)
        document = source.document
        analysis = source.analysis
        current = current_basis(document, knowledge)
        used = sorted(dependent_fact_ids(document.content))

        def value(item: object) -> str:
            if isinstance(item, (dict, list)):
                return json.dumps(item, ensure_ascii=False, sort_keys=True)
            return str(item)

        lines = [
            "# CV Decision and Provenance",
            "",
            f"- Application: {application.company} — {application.target_role}",
            f"- Application ID: `{application_id}`",
            f"- Document ID: `{document.id}`",
            f"- Document SHA-256: `{document.document_hash}`",
            f"- Preparation state: {preparation_state(document, current).value}",
            f"- Approved at: {document.approved_at if document.approved_basis == current else ''}",
            "",
            "## Classification",
            "",
            f"- Track: {analysis.track.value}",
            f"- Profile: {analysis.profile.value}",
            f"- Emphasis: {analysis.emphasis.value}",
            f"- Language: {analysis.language}",
            f"- Fit: {fit_level(analysis.requirements).value}",
            "",
            f"- User overrides: {value(analysis.user_override)}",
            "",
            "## Facts the content uses",
            "",
        ]
        lines.extend(f"- `{fact_id}`" for fact_id in used)
        if not used:
            lines.append("- None recorded")
        lines.extend(["", "## Facts the document depends on", ""])
        facts = knowledge.facts.facts
        for fact_id in sorted(dependent_fact_ids(document.content)):
            fact = facts.get(fact_id)
            lines.append(f"- `{fact_id}`: {fact.status.value if fact is not None else 'missing'}")
        report = document.content_report
        lines.extend(
            [
                "",
                "## Content report",
                "",
                f"- Content check: {content_check(document, current).value}",
                f"- Passed: {'' if report is None else report.passed}",
            ]
        )
        if report is not None:
            lines.extend(
                f"- {issue.group}/{issue.code}: {issue.message}" for issue in report.issues
            )
        lines.extend(
            [
                "",
                "## Exact lineage",
                "",
                f"- Job snapshot ID: `{source.job_snapshot_id}`",
                f"- Job analysis ID: `{document.analysis_id}`",
                f"- Built with Profile version: `{document.built_with.profile_version}`",
            ]
        )
        content = "\n".join(lines) + "\n"
        return DecisionMarkdownExport(
            application_id=application_id,
            document_id=document.id,
            filename=f"decision-{document.id}.md",
            content=content,
            content_hash=sha256_text(content),
        )
