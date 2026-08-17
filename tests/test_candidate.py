"""CandidateContext: identity by reference, and no candidate literals in code."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cv_engine.domain.candidate import (
    CANDIDATE_FILE,
    CandidateContextError,
    contact_href,
    load_candidate_context,
)
from cv_engine.domain.drafts import load_draft
from cv_engine.domain.facts import FactStore
from cv_engine.infrastructure.rendering import normalized_role_filename


ENGINE_DIR = Path(__file__).resolve().parent.parent / "cv_engine"

# The migration baseline and the legacy artifact inventory legitimately quote
# v1 evidence. Everything that decides what a rendered CV says must not.
POLICY_MODULES = (
    "domain/drafts.py",
    "domain/validation.py",
    "domain/selection.py",
    "domain/presentations.py",
    "domain/candidate.py",
    "domain/profiles.py",
    "domain/facts.py",
    "application/workflow.py",
    "application/ready.py",
    "infrastructure/rendering.py",
)
CANDIDATE_LITERALS = ("Matan Malka", "מתן מלכה", "matanmalka1", "matan1391")


def _candidate_file(root: Path) -> Path:
    return root / "base" / CANDIDATE_FILE


def _payload(root: Path) -> dict:
    return json.loads(_candidate_file(root).read_text(encoding="utf-8"))


def _write(root: Path, payload: dict) -> None:
    _candidate_file(root).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


# --- identity resolves from canonical facts ---------------------------------


def test_context_resolves_its_names_from_the_canonical_identity_fact(candidate_context) -> None:
    assert candidate_context.name_fact_id == "common.identity.name"
    assert candidate_context.display_name("en") == "Matan Malka"
    assert candidate_context.display_name("he") == "מתן מלכה"
    assert candidate_context.resolved_filename_name == "Matan Malka"
    assert len(candidate_context.version_hash) == 64


def test_the_recruiter_filename_uses_the_latin_name_for_a_hebrew_cv(candidate_context) -> None:
    assert normalized_role_filename("Account Executive", candidate_context) == (
        "Matan Malka - Account Executive - CV.pdf"
    )


def test_an_explicit_filename_override_wins(v1_repo: Path, fact_store: FactStore) -> None:
    payload = _payload(v1_repo)
    payload["filename_name"] = "M. Malka"
    _write(v1_repo, payload)
    context = load_candidate_context(v1_repo, fact_store)
    assert context.resolved_filename_name == "M. Malka"
    assert context.display_name("en") == "Matan Malka"


def test_the_version_hash_follows_the_facts_it_resolved(v1_repo: Path) -> None:
    """A changed contact rendering is a changed context, not a silent one."""
    before = load_candidate_context(v1_repo, FactStore.load(v1_repo / "base")).version_hash

    common = v1_repo / "base/common.md"
    text = common.read_text(encoding="utf-8")
    common.write_text(text.replace("linkedin.com/in/matanmalka1", "linkedin.com/in/other"), encoding="utf-8")

    after = load_candidate_context(v1_repo, FactStore.load(v1_repo / "base")).version_hash
    assert after != before


# --- contact policy ---------------------------------------------------------


def test_github_is_a_development_contact_only(candidate_context) -> None:
    sales = candidate_context.contacts_for_track("sales")
    development = candidate_context.contacts_for_track("development")

    assert "common.contact.github" not in sales
    assert development == [*sales, "common.contact.github"]
    assert sales[0] == "common.contact.location"


def test_contact_links_follow_the_declared_scheme(candidate_context) -> None:
    assert contact_href(candidate_context, "common.contact.location", "Tel Aviv") is None
    assert contact_href(candidate_context, "common.contact.email", "a@b.test") == "mailto:a@b.test"
    assert contact_href(candidate_context, "common.contact.phone", "+972-50-668-8386") == (
        "tel:+972506688386"
    )
    assert contact_href(candidate_context, "common.contact.linkedin", "linkedin.com/in/matanmalka1") == (
        "https://www.linkedin.com/in/matanmalka1"
    )


def test_a_drafted_document_takes_its_identity_from_the_context(drafted_application) -> None:
    setup = drafted_application("Context Co")
    document = load_draft(setup.manifest)

    assert document.name == "Matan Malka"
    assert [claim.fact_ids[0] for claim in document.contacts] == [
        "common.contact.location",
        "common.contact.phone",
        "common.contact.email",
        "common.contact.linkedin",
    ]


# --- refusals ---------------------------------------------------------------


def test_a_workspace_without_a_candidate_context_is_refused(v1_repo: Path, fact_store: FactStore) -> None:
    _candidate_file(v1_repo).unlink()
    with pytest.raises(CandidateContextError, match="no candidate context"):
        load_candidate_context(v1_repo, fact_store)


def test_an_unknown_or_non_canonical_fact_is_refused(v1_repo: Path, fact_store: FactStore) -> None:
    payload = _payload(v1_repo)
    payload["name_fact_id"] = "common.identity.absent"
    _write(v1_repo, payload)
    with pytest.raises(CandidateContextError, match="unusable fact"):
        load_candidate_context(v1_repo, fact_store)


def test_an_https_contact_without_a_target_is_refused(v1_repo: Path, fact_store: FactStore) -> None:
    payload = _payload(v1_repo)
    del payload["link_targets"]["common.contact.linkedin"]
    _write(v1_repo, payload)
    with pytest.raises(CandidateContextError, match="https link with no target"):
        load_candidate_context(v1_repo, fact_store)


def test_a_non_https_link_target_is_refused(v1_repo: Path, fact_store: FactStore) -> None:
    payload = _payload(v1_repo)
    payload["link_targets"]["common.contact.linkedin"] = "http://linkedin.com/in/x"
    _write(v1_repo, payload)
    with pytest.raises(CandidateContextError, match="non-https link target"):
        load_candidate_context(v1_repo, fact_store)


def test_link_policy_for_an_unused_contact_is_refused(v1_repo: Path, fact_store: FactStore) -> None:
    payload = _payload(v1_repo)
    payload["link_schemes"]["common.education.fullstack"] = "text"
    _write(v1_repo, payload)
    with pytest.raises(CandidateContextError, match="does not use"):
        load_candidate_context(v1_repo, fact_store)


# --- no candidate literals in policy code -----------------------------------


@pytest.mark.parametrize("module", POLICY_MODULES)
def test_policy_modules_contain_no_candidate_literal(module: str) -> None:
    source = (ENGINE_DIR / module).read_text(encoding="utf-8")
    found = [literal for literal in CANDIDATE_LITERALS if literal in source]
    assert not found, f"{module} hardcodes candidate data: {found}"
