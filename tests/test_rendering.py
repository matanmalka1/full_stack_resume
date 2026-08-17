from __future__ import annotations

from cv_engine.rendering import (
    _claim_recoverable,
    _launch_failure_message,
    normalized_role_filename,
)


def test_sandbox_blocked_browser_reports_cause_and_subset_command() -> None:
    message = _launch_failure_message(
        "TargetClosedError: BrowserType.launch\n"
        "bootstrap_check_in org.chromium.Chromium.rohitfork.1 failed: Permission denied (1100)"
    )
    assert "Mach port" in message
    assert "--no-sandbox" in message
    assert 'pytest -m "not browser"' in message


def test_missing_browser_install_is_not_reported_as_a_sandbox_block() -> None:
    message = _launch_failure_message("Executable doesn't exist at /path/headless_shell")
    assert "Mach port" not in message
    assert "playwright install chromium" in message
    assert 'pytest -m "not browser"' in message


def test_filename_normalization_does_not_add_seniority(candidate_context) -> None:
    assert normalized_role_filename("Senior Account Executive", candidate_context) == (
        "Matan Malka - Account Executive - CV.pdf"
    )
    assert normalized_role_filename("Full Stack Developer", candidate_context) == (
        "Matan Malka - Full Stack Developer - CV.pdf"
    )


def test_rtl_ats_comparison_accepts_bidi_token_reordering() -> None:
    source = "שיפור של כ-30% בביצועי הצוות ובהכנסות B2B לאורך התקופה"
    extracted = "בביצועי הצוות ובהכנסות 30% שיפור של כ B2B לאורך התקופה"
    assert _claim_recoverable(source, extracted.casefold(), rtl=True)
    assert not _claim_recoverable(source, "שיפור חלקי בלבד", rtl=True)
