from __future__ import annotations

from pathlib import Path

from cv_engine.domain.drafts import parse_draft
from cv_engine.infrastructure.artifacts import FilesystemArtifactStore
from cv_engine.runtime.workspace import load_workspace
from cv_engine.util import canonical_json, sha256_text
from cv_engine.compat import Engine


def artifact_store(root: Path) -> FilesystemArtifactStore:
    """The real artifact adapter for a test Workspace.

    Tests that need a draft on disk go through the same adapter the product
    uses, so no test carries its own copy of the storage layout.
    """
    return FilesystemArtifactStore(load_workspace(root))


def store_draft(root: Path, draft):
    """Write a working draft and return its Markdown path and exact text."""
    stored = artifact_store(root).write_working_draft(draft)
    return stored.paths.markdown, stored.markdown


ACCOUNT_MANAGER_JOB = (
    "Account Manager responsible for retention, portfolio growth, negotiation, "
    "and customer relationships."
)

# Hebrew, low confidence, one hard gap and one warning gap: the deterministic
# classifier requires approval here, so it exposes anything a provider could
# quietly relax.
AMBIGUOUS_HEBREW_JOB = (
    "דרוש מנהל לקוחות עם ניסיון בפיתוח עסקי ובניהול תיק לקוחות מול ארגונים גדולים. "
    "התפקיד כולל אחריות על שימור, גיוס לקוחות חדשים והובלת תהליכי מכירה מורכבים. "
    "דרישות: account manager, business development, Salesforce, must have direct saas sales."
)

PAYME_TECH_SALES_JOB = (
    "FinTech platform for small businesses. Strategic Partnerships Sales Manager "
    "responsible for new partner acquisition and outbound Sales to website builders, "
    "CRMs, marketplaces, and software providers that can embed financial products. "
    "Engage prospects by phone and email, understand their needs, offer tailored "
    "solutions, pitch the service, guide the Sales process through closing, onboard "
    "customers, and maintain Sales progress and follow-up tasks in our CRM system. "
    "Prefer inside Sales experience in a SaaS or tech-related industry."
)


def working_claim(engine: Engine, application_id: str, fact_id: str):
    manifest = engine.root / "artifacts/working" / application_id / "resume.claims.json"
    draft = parse_draft(manifest.read_text(encoding="utf-8"))
    return next(
        claim
        for section in draft.sections
        for claim in section.claims
        if fact_id in claim.fact_ids
    )


def exact_fact_claim(draft, fact_ids: list[str]):
    return next(
        claim
        for section in draft.sections
        for claim in section.claims
        if claim.fact_ids == fact_ids
    )


def claim_by_id(draft, claim_id: str):
    return next(
        claim
        for section in draft.sections
        for claim in section.claims
        if claim.claim_id == claim_id
    )


def artifact_version_and_path(
    engine: Engine,
    application_id: str,
    root: Path,
    artifact_type: str,
    lifecycle_status: str,
):
    version = engine.repo.latest_artifact_version(application_id, artifact_type, lifecycle_status)
    return version, root / version["path"]


def seal_report(report: dict) -> dict:
    sealed = dict(report)
    sealed.pop("report_hash", None)
    sealed["report_hash"] = sha256_text(canonical_json(sealed))
    return sealed


def passing_migration_test_runner(root: Path) -> Path:
    return root / "data/migration/migration-tests.json"
