from cv_engine.analysis import classify_job
from helpers import PAYME_TECH_SALES_JOB


def test_development_classification() -> None:
    result = classify_job("Backend software developer building Python APIs with React and PostgreSQL")
    assert result.track.value == "development"
    assert result.profile.value == "development"
    assert result.fit.value == "high"


def test_sales_profile_and_salesforce_warning() -> None:
    result = classify_job("Account Manager responsible for customer relationships, retention, portfolio growth, and Salesforce")
    assert result.track.value == "sales"
    assert result.profile.value == "account-manager"
    assert result.fit.value == "medium"
    assert result.gaps[0].requirement == "Salesforce"
    assert "sales.tool.priority" in result.gaps[0].substitute_fact_ids


def test_direct_saas_requirement_is_hard_gap() -> None:
    result = classify_job("Account Executive. Must have proven direct SaaS Sales experience and closing quota.")
    assert result.fit.value == "low"
    assert any(gap.requirement == "Direct SaaS Sales" and gap.severity == "hard" for gap in result.gaps)


def test_hebrew_language_detection_and_override() -> None:
    result = classify_job("דרוש מנהל תיקי לקוחות לעבודה מול לקוחות עסקיים ושימור קשרים")
    assert result.language == "he"
    overridden = classify_job("developer Python API", language_override="he")
    assert overridden.language == "he"
    assert overridden.user_override["language"] == "he"


def test_tech_sales_analysis_records_preference_gaps_and_selection_concepts() -> None:
    result = classify_job(
        PAYME_TECH_SALES_JOB,
        track_override="tech-sales",
        profile_override="tech-sales",
        emphasis_override="new-business",
    )

    assert result.fit.value == "medium"
    gaps = {gap.requirement: gap for gap in result.gaps}
    assert gaps["Direct SaaS Sales preference"].severity == "warning"
    assert gaps["Sales CRM usage"].substitute_fact_ids == [
        "sales.leadership.pipeline",
        "sales.tool.priority",
        "development.phdigital.crm",
    ]
    assert gaps["Strategic partnerships / channel Sales experience"].severity == "warning"
    assert {
        "closing",
        "communication",
        "crm",
        "discovery",
        "integrations",
        "new-business",
        "onboarding",
        "pipeline",
        "prospecting",
        "technical",
    } <= set(result.keywords)
