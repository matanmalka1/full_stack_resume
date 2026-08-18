"""CandidateContext: identity by reference, and no candidate literals in code."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from cv_engine.domain.candidate import CANDIDATE_FILE, CandidateContextError, contact_href
from cv_engine.domain.draft_markdown import parse_draft
from cv_engine.domain.facts import FactStore
from cv_engine.infrastructure.knowledge import load_candidate_context, load_fact_store
from cv_engine.infrastructure.rendering import normalized_role_filename


ENGINE_DIR = Path(__file__).resolve().parent.parent / "cv_engine"

# Every module is policy unless it is one of these two, which quote v1 evidence
# on purpose: the canonical source writer and the legacy migration mapping. An
# inclusion list had to be extended for each new module and silently stopped
# covering anything nobody remembered to add.
CANDIDATE_EVIDENCE_MODULES = frozenset(
    {
        "infrastructure/canonical_data.py",
        "infrastructure/migration.py",
    }
)
CANDIDATE_LITERALS = ("Matan Malka", "מתן מלכה", "matanmalka1", "matan1391")


def _candidate_file(root: Path) -> Path:
    return root / "base" / CANDIDATE_FILE


def _payload(root: Path) -> dict:
    return json.loads(_candidate_file(root).read_text(encoding="utf-8"))


def _write(root: Path, payload: dict) -> None:
    _candidate_file(root).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


# --- identity resolves from canonical facts ---------------------------------


def test_context_resolves_identity_filename_and_track_contact_policy(candidate_context) -> None:
    # New v2 facts carry UUIDv4 technical identity; the context references it.
    uuid.UUID(candidate_context.name_fact_id)
    assert candidate_context.display_name("en") == "Matan Malka"
    assert candidate_context.display_name("he") == "מתן מלכה"
    assert candidate_context.resolved_filename_name == "Matan Malka"
    assert len(candidate_context.version_hash) == 64
    assert normalized_role_filename("Account Executive", candidate_context) == (
        "Matan Malka - Account Executive - CV.pdf"
    )
    sales = candidate_context.contacts_for_track("sales")
    development = candidate_context.contacts_for_track("development")
    assert "common.contact.github" not in sales
    assert development == [*sales, "common.contact.github"]
    assert sales[0] == "common.contact.location"
    assert contact_href(candidate_context, "common.contact.location", "Tel Aviv") is None
    assert contact_href(candidate_context, "common.contact.email", "a@b.test") == "mailto:a@b.test"
    assert contact_href(candidate_context, "common.contact.phone", "+972-50-668-8386") == (
        "tel:+972506688386"
    )
    assert contact_href(
        candidate_context, "common.contact.linkedin", "linkedin.com/in/matanmalka1"
    ) == ("https://www.linkedin.com/in/matanmalka1")


def test_filename_override_and_dependency_hash_follow_canonical_context(
    v1_repo: Path, fact_store: FactStore
) -> None:
    payload = _payload(v1_repo)
    payload["filename_name"] = "M. Malka"
    _write(v1_repo, payload)
    context = load_candidate_context(v1_repo, fact_store)
    assert context.resolved_filename_name == "M. Malka"
    assert context.display_name("en") == "Matan Malka"

    before = context.version_hash
    common = v1_repo / "base/common.md"
    text = common.read_text(encoding="utf-8")
    common.write_text(
        text.replace("linkedin.com/in/matanmalka1", "linkedin.com/in/other"), encoding="utf-8"
    )
    after = load_candidate_context(v1_repo, load_fact_store(v1_repo / "base")).version_hash
    assert after != before


def test_a_drafted_document_takes_its_identity_from_the_context(drafted_application) -> None:
    setup = drafted_application("Context Co")
    document = parse_draft(setup.manifest.read_text(encoding="utf-8"))

    assert document.name == "Matan Malka"
    assert [claim.fact_ids[0] for claim in document.contacts] == [
        "common.contact.location",
        "common.contact.phone",
        "common.contact.email",
        "common.contact.linkedin",
    ]


# --- refusals ---------------------------------------------------------------


def test_candidate_context_rejects_missing_or_unusable_identity(
    v1_repo: Path, fact_store: FactStore
) -> None:
    original = _payload(v1_repo)
    _candidate_file(v1_repo).unlink()
    with pytest.raises(CandidateContextError, match="no candidate context"):
        load_candidate_context(v1_repo, fact_store)
    payload = dict(original)
    payload["name_fact_id"] = "00000000-0000-4000-8000-000000000000"
    _write(v1_repo, payload)
    with pytest.raises(CandidateContextError, match="unusable fact"):
        load_candidate_context(v1_repo, fact_store)


# --- no candidate literals in policy code -----------------------------------


def test_no_module_carries_a_candidate_literal_except_declared_evidence() -> None:
    """The candidate lives in Knowledge, not in code.

    Scanned across the whole engine rather than a listed subset, because the
    listed-subset form could only protect modules someone remembered to add — and
    a renderer, record, or projection added later is exactly where a literal would
    reappear.
    """
    offenders = {
        relative: [literal for literal in CANDIDATE_LITERALS if literal in source]
        for path in sorted(ENGINE_DIR.rglob("*.py"))
        if (relative := path.relative_to(ENGINE_DIR).as_posix()) not in CANDIDATE_EVIDENCE_MODULES
        and any(
            literal in (source := path.read_text(encoding="utf-8"))
            for literal in CANDIDATE_LITERALS
        )
    }
    assert not offenders, offenders
    # The exemptions must stay real, or the rule has quietly become decoration.
    for relative in sorted(CANDIDATE_EVIDENCE_MODULES):
        source = (ENGINE_DIR / relative).read_text(encoding="utf-8")
        assert any(literal in source for literal in CANDIDATE_LITERALS), (
            f"{relative} is exempt but carries no candidate literal; drop the exemption"
        )
