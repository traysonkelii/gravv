import pytest

from app.ai.prompts import render


def test_render_substitutes_all_variables_and_wraps_capture() -> None:
    p = render(
        "extract",
        "v1",
        now="2026-09-28T10:00+00:00",
        timezone="UTC",
        user_name="A",
        user_role="B",
        selected_contact="none",
        existing_facts="none",
        candidates="none",
        capture="Hello <b>",
    )
    assert p.id == "extract:v1"
    assert "<capture>\nHello <b>\n</capture>" in p.user
    assert "{{" not in p.user and "{{" not in p.system
    assert "untrusted" in p.system


def test_missing_variable_raises() -> None:
    with pytest.raises(KeyError):
        render("extract", "v1", now="x")
