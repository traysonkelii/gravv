"""Deterministic stand-in for the LLM. Rule-based extraction over the rendered prompt so local development and
tests behave the same every run. Fixture files (tests/fixtures/ai/<prompt>/<hash>.json) override the heuristics
for specific inputs."""

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.ai.extraction import (
    BriefDraft,
    BriefStructured,
    CaptureExtraction,
    ContactMatch,
    ContactProfileDraft,
    ExtractedFact,
    ExtractedInteraction,
    ExtractedTask,
    MentionedPerson,
)
from app.ai.prompts import Prompt
from app.db.enums import FactCategory, InteractionKind, SentimentLabel

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "ai"
HONORIFICS = {"colonel": "col.", "general": "gen.", "doctor": "dr.", "major": "maj.", "captain": "capt."}
POSITIVE = {"great", "pleased", "happy", "excited", "good", "loves", "positive", "credited", "thanked", "well"}
NEGATIVE = {"worried", "concerned", "upset", "frustrated", "angry", "cut short", "declined", "no reply", "bad"}
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
TASK_RE = re.compile(
    r"\b(?:remind me to|reminder to|i need to|need to|follow up (?:with|on)"
    r"|schedule (?=(?:a|an|the|my|our)\b)|book (?=(?:a|an|the|my|our)\b)|send (?:him|her|them)\s)"
    r"\s*([^.;,]+)",
    re.I,
)
FACT_RE = re.compile(
    r"\b(he|she|they|He|She|They|[A-Z][a-z]+)\s+"
    r"(is a|is an|is|are|loves?|likes?|prefers?|hates?|dislikes?|drinks?|enjoys?|plays?|collects?|runs?)\s+([^.;,]+)"
)
PERSON_RE = re.compile(r"\b((?:Maj|Capt|Col|Dr|Gen|Mr|Ms|Lt)\.?\s+)?([A-Z][a-z]+)\s+([A-Z][a-z]+)\b")
STOP_WORDS = {"Diet", "Coke", "North", "Carolina", "Space", "Force", "Phase", "Program", "Next", "The", "Met", "Update"}


def _section(user: str, header: str, until: str) -> str:
    start = user.find(header)
    if start < 0:
        return ""
    start += len(header)
    end = user.find(until, start) if until else -1
    return user[start : end if end >= 0 else None].strip()


def _fixture(prompt: Prompt) -> dict[str, Any] | None:
    digest = hashlib.sha256(prompt.user.encode()).hexdigest()[:12]
    path = FIXTURES / prompt.name / f"{digest}.json"
    if path.exists():
        return json.loads(path.read_text())  # type: ignore[no-any-return]
    return None


def input_hash(prompt: Prompt) -> str:
    return hashlib.sha256(prompt.user.encode()).hexdigest()[:12]


def _resolve_date(text: str, now: datetime) -> tuple[datetime | None, str | None]:
    t = text.lower()
    if "tomorrow" in t:
        return now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1), None
    m = re.search(r"in (\d+|thirty|two|three|seven|ten) days?", t)
    if m:
        words = {"thirty": 30, "two": 2, "three": 3, "seven": 7, "ten": 10}
        n = words.get(m.group(1)) or int(m.group(1)) if not m.group(1).isalpha() or m.group(1) in words else 7
        return now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=int(n)), None
    for i, day in enumerate(WEEKDAYS):
        if f"next {day}" in t or f"on {day}" in t or t.endswith(day):
            delta = (i - now.weekday()) % 7
            delta = 7 if delta == 0 else delta
            if f"next {day}" in t and delta < 7 and now.weekday() >= i:
                delta += 0
            return now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=delta), None
    if "next week" in t or "soon" in t or "later" in t:
        return (
            None,
            f"Unsure which date '{'next week' if 'next week' in t else 'soon'}' means; left the due date empty.",
        )
    return None, None


def _category(verb: str, obj: str) -> FactCategory:
    v = verb.lower()
    if v.startswith(("hate", "dislike")):
        return FactCategory.dislike
    if v.startswith(("prefer", "drink")):
        return FactCategory.preference
    if v.startswith(("love", "like", "enjoy", "play", "collect", "run")):
        return FactCategory.interest
    o = obj.lower()
    if any(k in o for k in ("kid", "wife", "husband", "daughter", "son", "married", "family")):
        return FactCategory.family
    if any(k in o for k in ("fanatic", "fan", "runner", "golfer", "collector", "player")):
        return FactCategory.interest
    if any(k in o for k in ("director", "manager", "owns", "budget", "program", "vp", "chief")):
        return FactCategory.professional
    return FactCategory.personal


def _clean_fact(verb: str, obj: str) -> str:
    v = verb.lower().rstrip("s") if verb.lower() not in ("is", "are", "is a", "is an") else ""
    obj = obj.strip().rstrip(".")
    if v in ("love", "like", "enjoy", "prefer", "drink", "hate", "dislike", "play", "collect", "run"):
        text = (
            f"{v.capitalize()}s {obj}"
            if v in ("love", "like", "enjoy", "prefer", "drink", "hate", "dislike", "play", "collect", "run")
            else obj
        )
        if v == "love" or v == "like" or v == "enjoy":
            text = obj[0].upper() + obj[1:]
        return text
    return obj[0].upper() + obj[1:]


def fake_extract(prompt: Prompt) -> CaptureExtraction:
    user = prompt.user
    now_text = _section(user, "Current datetime:", "\n")
    try:
        now = datetime.fromisoformat(now_text.split(" (")[0].strip())
    except ValueError:
        now = datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    selected = _section(user, "Selected contact (may be empty):", "\n\nExisting facts")
    existing = _section(user, "(do not repeat these):", "\n\nCandidate contacts").lower()
    candidates_raw = _section(user, "(id, name, company, title):", "\n\n<capture>")
    capture = _section(user, "<capture>", "</capture>")
    lower = capture.lower()

    candidates: list[tuple[str, str]] = []
    for line in candidates_raw.splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 2 and parts[0] and parts[0] not in ("none", "-"):
            candidates.append((parts[0], parts[1]))

    match: ContactMatch | None = None
    for cid, name in candidates:
        tokens = [t for t in re.split(r"[\s.]+", name.lower()) if len(t) > 2]
        surname = tokens[-1] if tokens else ""
        honorific = tokens[0] if tokens and tokens[0] in {"col", "gen", "dr", "maj", "capt"} else ""
        hon_word = next((w for w, h in HONORIFICS.items() if h.rstrip(".") == honorific), "")
        if (surname and re.search(rf"\b{re.escape(surname)}\b", lower)) or (hon_word and f"the {hon_word}" in lower):
            match = ContactMatch(contact_id=cid, display_name=name, confidence=0.92 if surname in lower else 0.8)
            break
    if match is None and selected and selected.lower() not in ("none", "(none)", ""):
        parts = [p.strip() for p in selected.split("|")]
        if len(parts) >= 2:
            match = ContactMatch(contact_id=parts[0], display_name=parts[1], confidence=0.95)

    kind = InteractionKind.note
    if re.search(r"\b(met|meeting|lunch|dinner|visited|sat down)\b", lower):
        kind = InteractionKind.meeting
    elif re.search(r"\b(call|called|phone|spoke)\b", lower):
        kind = InteractionKind.call
    elif re.search(r"\b(email|emailed|wrote)\b", lower):
        kind = InteractionKind.email
    elif re.search(r"\b(texted|messaged|message)\b", lower):
        kind = InteractionKind.message
    occurred: datetime | None = None
    if "yesterday" in lower:
        occurred = now - timedelta(days=1)
    elif "this morning" in lower:
        occurred = now.replace(hour=9, minute=0, second=0, microsecond=0)
    pos = sum(1 for w in POSITIVE if w in lower)
    neg = sum(1 for w in NEGATIVE if w in lower)
    score = max(-1.0, min(1.0, (pos - neg) * 0.3))
    label = (
        SentimentLabel.positive
        if score > 0.15
        else SentimentLabel.negative
        if score < -0.15
        else (SentimentLabel.mixed if pos and neg else SentimentLabel.neutral)
    )
    first_sentence = re.split(r"(?<=[.!?])\s+", capture.strip())[0][:200] if capture.strip() else ""
    interaction = ExtractedInteraction(
        kind=kind,
        occurred_at=occurred,
        subject=(first_sentence[:80] if first_sentence else "Note"),
        summary=first_sentence,
        body=capture.strip(),
        sentiment=label,
        sentiment_score=score,
    )

    facts: list[ExtractedFact] = []
    seen: set[str] = set()
    for m in FACT_RE.finditer(capture):
        subject, verb, obj = m.group(1), m.group(2), m.group(3)
        if subject.lower() not in ("he", "she", "they") and subject in STOP_WORDS | {"The", "This", "It"}:
            continue
        content = _clean_fact(verb, obj)
        key = content.lower()
        if key in seen or len(content) < 3:
            continue
        if key in existing or any(key in line for line in existing.splitlines()):
            continue
        seen.add(key)
        facts.append(ExtractedFact(category=_category(verb, obj), content=content, confidence=0.85))

    tasks: list[ExtractedTask] = []
    needs_review: list[str] = []
    for m in TASK_RE.finditer(capture):
        raw = m.group(1).strip()
        due, note = _resolve_date(raw, now)
        title = re.sub(r"\s+(next|on|by|in)\s+(\w+day|week|\d+ days?|thirty days|tomorrow).*$", "", raw, flags=re.I).strip()
        title = title[0].upper() + title[1:] if title else raw
        tasks.append(ExtractedTask(title=title[:200], due_at=due, priority=2))
        if note:
            needs_review.append(note)

    people: list[MentionedPerson] = []
    known = {n.lower() for _c, n in candidates} | ({match.display_name.lower()} if match else set())
    for m in PERSON_RE.finditer(capture):
        first, last = m.group(2), m.group(3)
        if first in STOP_WORDS or last in STOP_WORDS:
            continue
        name = f"{(m.group(1) or '').strip()} {first} {last}".strip()
        if any(last.lower() in k for k in known):
            continue
        if name.lower() not in {p.name.lower() for p in people}:
            people.append(MentionedPerson(name=name))

    return CaptureExtraction(
        contact_match=match,
        interaction=interaction,
        facts=facts[:20],
        tasks=tasks[:20],
        mentioned_people=people[:20],
        needs_review=needs_review[:10],
    )


def fake_profile(prompt: Prompt) -> ContactProfileDraft:
    user = prompt.user
    contact = _section(user, "Contact:", "\n")
    interests = [i.strip().lower() for i in _section(user, "Practitioner interests:", "\n").split(",") if i.strip()]
    facts = [
        line.strip("- ").strip()
        for line in _section(user, "Active facts:", "\n\nRecent interactions").splitlines()
        if line.strip() and line.strip() not in ("none", "(none)")
    ]
    interactions = [
        line
        for line in _section(user, "(newest first):", "\n\nOpen tasks").splitlines()
        if line.strip() and line.strip() not in ("none", "(none)")
    ]
    style = next((f.split(":", 1)[1].strip() for f in facts if f.lower().startswith("communication_style:")), "")
    plain = [f.split(":", 1)[1].strip() if ":" in f else f for f in facts]
    risks = [f.split(":", 1)[1].strip() for f in facts if f.lower().startswith("risk:")]
    interest_facts = [f.split(":", 1)[1].strip() for f in facts if f.lower().startswith(("interest:", "preference:"))]
    common = [i for i in interests if any(i in f.lower() for f in plain)][:3]
    summary = (
        f"{contact}. {len(interactions)} recent interaction{'s' if len(interactions) != 1 else ''}"
        f"{', most recently ' + interactions[0].split(' | ')[0] if interactions else ''}. "
        f"{'Worth remembering: ' + '; '.join(plain[:3]) + '.' if plain else 'No notes to remember yet.'}"
    )
    return ContactProfileDraft(
        summary=summary[:900],
        communication_style=style[:120],
        remember=[p[:80] for p in plain if not p.lower().startswith("communication")][:8],
        risks=risks[:4],
        talking_points=[f"Ask about {i.lower()}" for i in interest_facts[:5]] or ["Ask what has changed since you last spoke"],
        common_ground=[c.capitalize() for c in common],
    )


def fake_brief(prompt: Prompt) -> BriefDraft:
    user = prompt.user
    contact = _section(user, "Contact:", "\n")
    tasks = [
        line.strip("- ")
        for line in _section(user, "Open tasks:", "\n\nOpen opportunities").splitlines()
        if line.strip() and line.strip() not in ("none", "(none)")
    ]
    timeline = [
        line
        for line in _section(user, "(newest first):", "\n\nOpen tasks").splitlines()
        if line.strip() and line.strip() not in ("none", "(none)")
    ]
    text = (
        f"Where things stand\n{contact}. {len(timeline)} touchpoints in the last 90 days"
        f"{', the latest ' + timeline[0] if timeline else ''}.\n\n"
        f"Open items\n{'; '.join(tasks) if tasks else 'Nothing outstanding on your side.'}\n\n"
        "What to bring up\nConfirm next steps and the timeline they care about.\n\n"
        "Watch for\nAnything that has changed in their organization since the last conversation."
    )
    return BriefDraft(
        text=text[:2400],
        structured=BriefStructured(
            due_outs=tasks[:10],
            suggested_questions=[
                "What has changed on your side since we last spoke?",
                "What would make the next month a success for you?",
            ],
        ),
    )


def fake_structured(prompt: Prompt, schema: type[Any]) -> Any:
    fixture = _fixture(prompt)
    if fixture is not None:
        return schema.model_validate(fixture)
    if schema is CaptureExtraction:
        return fake_extract(prompt)
    if schema is ContactProfileDraft:
        return fake_profile(prompt)
    if schema is BriefDraft:
        return fake_brief(prompt)
    raise TypeError(f"fake provider has no strategy for {schema.__name__}")
