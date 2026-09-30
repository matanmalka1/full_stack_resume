from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from helpers import approve_active_draft, seed_document, seed_draft, stored_document

from cv_engine.application.commands import RenderCommand
from cv_engine.domain.draft_markdown import serialize_markdown
from cv_engine.domain.drafts import draft_claims
from cv_engine.infrastructure.rendering import render_html
from cv_engine.util import sha256_text

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "golden"


def _front_matter_and_body(markdown: str) -> tuple[str, str]:
    """Split the provenance header from the document itself.

    The header carries knowledge versions, which legitimately move whenever a
    fact is added anywhere in the store. Pinning the body separately keeps the
    golden comparison about content: a changed claim, contact, section, or name
    still fails, while a knowledge-version bump is asserted against the live
    store instead of being frozen into a hash nobody can interpret later.
    """
    front, _, body = markdown.partition("\n---\n")
    return front, body


def _golden_cases() -> list[tuple[Path, dict]]:
    return [
        (fixture, json.loads(fixture.read_text(encoding="utf-8")))
        for fixture in sorted(GOLDEN_DIR.glob("*.json"))
    ]


def _golden_choice(profile, case: dict) -> dict[str, list[str]]:
    """The facts each section keeps, standing in for the writer's choice.

    Fixture input, not a computed selection: the golden cases pin what a document
    with these facts renders to, while `draft_resume` owns the choice itself.
    """
    kept = set(case["snapshot"]["fact_ids"])
    return {
        spec.name_en: [fact_id for fact_id in spec.fact_ids if fact_id in kept]
        for spec in profile.sections
    }


def _build_case(services, case: dict):
    overrides = case.get("overrides", {})
    ingested, analysed = seed_document(
        services,
        f"Golden {case['profile']} {case['language']}",
        job_text=case["job"],
        track_override=overrides.get("track") or case["track"],
        profile_override=overrides.get("profile") or case["profile"],
        emphasis_override=overrides.get("emphasis") or case["emphasis"],
        language_override=overrides.get("language") or case["language"],
    )
    knowledge = services.knowledge.load()
    seed_draft(
        services,
        ingested.application_id,
        _golden_choice(knowledge.profiles.get(analysed.analysis.profile), case),
    )
    document = stored_document(services, ingested.application_id)
    return SimpleNamespace(
        facts=knowledge.facts,
        analysis=analysed.analysis,
        draft=document.content,
        candidate=knowledge.candidate,
        profile=knowledge.profiles.get(analysed.analysis.profile),
        document=document,
    )


def test_representative_profiles_match_their_golden_ready_outputs(
    project_root: Path,
    tmp_path: Path,
    services,
) -> None:
    """Pin content: analysis fields, the chosen facts, Markdown, and rendered HTML.

    Nothing here needs a browser. `render_html` writes the document itself; only
    PDF geometry and the ATS/layout report below it need Chromium, and they are
    a separate test so this hash comparison runs in the default suite.
    """
    for fixture, case in _golden_cases():
        setup = _build_case(services, case)
        facts, analysis, draft = setup.facts, setup.analysis, setup.draft
        used = sorted({fact_id for claim in draft_claims(draft) for fact_id in claim.fact_ids})
        candidate = setup.candidate
        assert analysis.track.value == case["track"], fixture.stem
        assert analysis.profile.value == case["profile"], fixture.stem
        assert analysis.emphasis.value == case["emphasis"], fixture.stem
        assert analysis.language == case["language"], fixture.stem
        markdown = serialize_markdown(draft)
        assert "30% YoY" not in markdown, fixture.stem
        assert "3-4 sales representatives" not in markdown.casefold(), fixture.stem
        assert all(facts.get(fact_id).status.value == "canonical" for fact_id in used), fixture.stem
        if case["language"] == "he":
            assert "תקציר מקצועי" in markdown
            assert "עברית: שפת אם" in markdown
        if case["track"] == "tech-sales":
            assert "Full-Stack Developer | PH.Digital" in markdown
            assert "direct SaaS Sales" not in markdown

        target = tmp_path / fixture.stem
        target.mkdir()
        html = render_html(draft, project_root, target / "resume.html", candidate)
        html_text = html.read_text(encoding="utf-8")
        front_matter, markdown_body = _front_matter_and_body(markdown)
        assert f'fact_store_version: "{facts.version}"' in front_matter
        assert draft.fact_store_version == facts.version
        snapshot = {
            "markdown_body_sha256": sha256_text(markdown_body),
            "html_sha256": sha256_text(html_text),
            "fact_ids": used,
            "sections": [section.name for section in draft.sections],
        }
        assert snapshot == case["snapshot"], fixture.stem
        assert "<ul>" not in html_text
        assert html_text.count('class="bullet claim"') == sum(
            claim.style == "bullet" for section in draft.sections for claim in section.claims
        )
        if case["language"] == "he":
            assert '<html lang="he" dir="rtl">' in html_text
            assert '<bdi dir="ltr">B2B</bdi>' in html_text


def test_golden_outputs_pass_render_validation(
    project_root: Path,
    tmp_path: Path,
    services,
    render_validator,
) -> None:
    """The same documents must survive PDF rendering and the layout/ATS report.

    Browser-marked through `render_validator`. It re-asserts the golden
    `html_sha256` before validating, so this proves the report was produced from
    the exact bytes the hash test pinned rather than from a document that drifted.
    """
    for fixture, case in _golden_cases():
        setup = _build_case(services, case)

        approved = approve_active_draft(services, setup.document.application_id)
        assert approved.passed, approved.report
        rendered = services.rendering.render(
            RenderCommand(
                application_id=setup.document.application_id,
                expected_document_hash=setup.document.document_hash,
            )
        )
        document = stored_document(services, setup.document.application_id)
        assert document.html_path is not None
        html = services.paths.root / document.html_path
        assert sha256_text(html.read_text(encoding="utf-8")) == case["snapshot"]["html_sha256"], (
            fixture.stem
        )
        assert rendered.validation.passed, rendered.validation.model_dump()
        assert rendered.validation.evidence["page_count"] in {1, 2}
