"""Deterministic relationship score (Section 7.9). Pure functions; the SQL that gathers inputs lives in compute.py."""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from math import exp, log
from typing import Any

from app.db.enums import Band, ContactStatus
from app.scoring.bands import band_for

WEIGHTS = {"recency": 0.35, "frequency": 0.20, "sentiment": 0.15, "reciprocity": 0.10, "depth": 0.10, "momentum": 0.10}


@dataclass(frozen=True)
class InteractionPoint:
    occurred_at: datetime
    direction: str  # inbound | outbound | mutual
    sentiment_score: float | None


@dataclass(frozen=True)
class ScoreInputs:
    cadence_days: int
    interactions: list[InteractionPoint] = field(default_factory=list)  # last 180 days, newest first
    active_facts: int = 0
    communication_style_known: bool = False
    overdue_tasks: int = 0
    tasks_due_within_3_days: int = 0
    earliest_open_task_due: datetime | None = None
    open_opportunity_count: int = 0
    open_opportunity_value_cents: int = 0
    score_30d_ago: int | None = None
    previous_score: int | None = None
    archived: bool = False


@dataclass(frozen=True)
class ScoreResult:
    score: int
    band: Band
    status: ContactStatus
    next_due_at: datetime | None
    components: dict[str, Any]
    days_since_last: float | None
    delta_30d: int | None


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def compute(inputs: ScoreInputs, now: datetime | None = None) -> ScoreResult:
    now = now or datetime.now(UTC)
    cadence = max(1, inputs.cadence_days)
    pts = sorted(inputs.interactions, key=lambda p: p.occurred_at, reverse=True)
    last = pts[0].occurred_at if pts else None
    days_since_last = (now - last).total_seconds() / 86400 if last else None

    recency = exp(-log(2) * days_since_last / cadence) if days_since_last is not None else 0.0

    n90 = sum(1 for p in pts if (now - p.occurred_at).days < 90)
    expected = 90 / cadence
    frequency = clamp(n90 / expected, 0, 1.5) / 1.5 if expected > 0 else 0.0

    recent_scores = [p.sentiment_score for p in pts[:10] if p.sentiment_score is not None]
    mean_sent = sum(recent_scores) / len(recent_scores) if recent_scores else 0.0
    sentiment = (mean_sent + 1) / 2

    last20 = pts[:20]
    if len(last20) >= 3:
        inbound = sum(1.0 if p.direction == "inbound" else 0.5 if p.direction == "mutual" else 0.0 for p in last20)
        inbound_share = inbound / len(last20)
        reciprocity = 1 - abs(0.5 - inbound_share) * 2
    else:
        reciprocity = 0.5

    depth = min(inputs.active_facts, 10) / 10 * 0.7 + (0.3 if inputs.communication_style_known else 0.0)

    delta_30d: int | None = None
    if inputs.score_30d_ago is not None and inputs.previous_score is not None:
        delta_30d = inputs.previous_score - inputs.score_30d_ago
    sign = 0 if not delta_30d else (1 if delta_30d > 0 else -1)
    momentum = clamp(0.5 + 0.25 * sign * min(abs(delta_30d or 0) / 20, 1) - 0.25 * min(inputs.overdue_tasks, 2) / 2, 0, 1)

    components = {
        "recency": recency,
        "frequency": frequency,
        "sentiment": sentiment,
        "reciprocity": reciprocity,
        "depth": depth,
        "momentum": momentum,
    }
    score = round(100 * sum(WEIGHTS[k] * v for k, v in components.items()))
    score = int(clamp(score, 0, 100))

    band = band_for(score, last, cadence, now)

    cadence_due = last + timedelta(days=cadence) if last else None
    candidates = [d for d in (inputs.earliest_open_task_due, cadence_due) if d is not None]
    next_due_at = min(candidates) if candidates else None

    if inputs.archived:
        status = ContactStatus.archived
    elif band in (Band.weak, Band.drifting) or (delta_30d is not None and delta_30d <= -10):
        status = ContactStatus.needs_attention
    elif inputs.overdue_tasks > 0 or inputs.tasks_due_within_3_days > 0 or (days_since_last is not None and days_since_last >= cadence):
        status = ContactStatus.follow_up
    else:
        status = ContactStatus.active

    rounded = {k: round(v, 4) for k, v in components.items()}
    return ScoreResult(
        score=score,
        band=band,
        status=status,
        next_due_at=next_due_at,
        components=rounded,
        days_since_last=days_since_last,
        delta_30d=delta_30d,
    )
