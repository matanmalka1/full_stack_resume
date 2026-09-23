"""CandidateContext: identity resolves by reference to canonical facts."""

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


def _candidate_file(root: Path) -> Path:
    return root / "base" / CANDIDATE_FILE


def _payload(root: Path) -> dict:
    return json.loads(_candidate_file(root).read_text(encoding="utf-8"))


def _write(root: Path, payload: dict) -> None:
    _candidate_file(root).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


# --- identity resolves from canonical facts ---------------------------------


def test_context_resolves_identity_filename_track_contacts_and_dependency_hash(
    candidate_context, project_root: Path, fact_store: FactStore
) -> None:
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

    payload = _payload(project_root)
    payload["filename_name"] = "M. Malka"
    _write(project_root, payload)
    overridden = load_candidate_context(project_root, fact_store)
    assert overridden.resolved_filename_name == "M. Malka"
    assert overridden.display_name("en") == "Matan Malka"

    before = overridden.version_hash
    common = project_root / "base/common.json"
    text = common.read_text(encoding="utf-8")
    common.write_text(
        text.replace("linkedin.com/in/matanmalka1", "linkedin.com/in/other"), encoding="utf-8"
    )
    after = load_candidate_context(
        project_root, load_fact_store(project_root / "base")
    ).version_hash
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
    project_root: Path, fact_store: FactStore
) -> None:
    original = _payload(project_root)
    _candidate_file(project_root).unlink()
    with pytest.raises(CandidateContextError, match="no candidate context"):
        load_candidate_context(project_root, fact_store)
    payload = dict(original)
    payload["name_fact_id"] = "00000000-0000-4000-8000-000000000000"
    _write(project_root, payload)
    with pytest.raises(CandidateContextError, match="unusable fact"):
        load_candidate_context(project_root, fact_store)
