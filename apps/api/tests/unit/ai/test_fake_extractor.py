from datetime import datetime

from app.ai.extraction import CaptureExtraction
from app.ai.fake import fake_extract
from app.ai.prompts import render

CANDIDATES = (
    "00000000-0000-4000-8000-0000000000a1 | Col. Michael Johnson | Space Force | Program Director\n"
    "00000000-0000-4000-8000-0000000000a5 | Dr. James Chen | NASA | Chief Scientist"
)


def _prompt(capture: str, selected: str = "none", existing: str = "none") -> CaptureExtraction:
    p = render(
        "extract",
        "v1",
        now="2026-09-28T14:30-04:00",
        timezone="America/New_York",
        user_name="Sarah Chen",
        user_role="Account Executive",
        selected_contact=selected,
        existing_facts=existing,
        candidates=CANDIDATES,
        capture=capture,
    )
    return fake_extract(p)


def test_reference_scenario_yields_one_fact_and_one_task() -> None:
    out = _prompt("Met the Colonel, he loves competitive pinball, remind me to call the program officers next Tuesday")
    assert out.contact_match is not None and out.contact_match.display_name == "Col. Michael Johnson"
    assert out.interaction.kind == "meeting"
    assert [f.content for f in out.facts] == ["Competitive pinball"]
    assert out.facts[0].category == "interest"
    assert [t.title for t in out.tasks] == ["Call the program officers"]
    due = out.tasks[0].due_at
    assert (
        isinstance(due, datetime)
        and due.strftime("%A") == "Tuesday"
        and due > datetime.fromisoformat("2026-09-28T14:30-04:00")
    )
    assert out.needs_review == []


def test_selected_contact_wins_when_no_name_in_text() -> None:
    out = _prompt(
        "Quick call. She prefers early morning meetings.",
        selected="00000000-0000-4000-8000-0000000000a3 | Sarah Martinez | Lockheed Martin | VP Sales",
    )
    assert out.contact_match is not None and out.contact_match.contact_id.endswith("a3")
    assert out.interaction.kind == "call"
    assert out.facts[0].category == "preference"


def test_existing_facts_are_not_repeated() -> None:
    out = _prompt("Talked with Dr. Chen, he loves amateur astronomy.", existing="- interest: Amateur astronomy")
    assert out.facts == []


def test_vague_dates_go_to_needs_review() -> None:
    out = _prompt("Emailed Johnson. Need to send the revised cost sheet next week.")
    assert out.tasks and out.tasks[0].due_at is None
    assert out.needs_review and "next week" in out.needs_review[0]


def test_mentioned_people_exclude_known_contacts() -> None:
    out = _prompt("Met Johnson; he mentioned Maj. Lisa Park and Capt. Omar Reyes will own the test plan.")
    names = {p.name for p in out.mentioned_people}
    assert names == {"Maj. Lisa Park", "Capt. Omar Reyes"}


def test_no_candidate_match_returns_null() -> None:
    out = _prompt("Coffee with Ben Okoro about his fund.")
    assert out.contact_match is None
    assert any(p.name == "Ben Okoro" for p in out.mentioned_people)
