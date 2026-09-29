"""Table-driven cases for the score engine, including the boundaries in Section 7.9."""

from datetime import UTC, datetime, timedelta

import pytest

from app.db.enums import Band, ContactStatus
from app.scoring.gravity import InteractionPoint, ScoreInputs, compute

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def pts(*days_ago: float, direction: str = "mutual", sentiment: float | None = 0.5) -> list[InteractionPoint]:
    return [InteractionPoint(NOW - timedelta(days=d), direction, sentiment) for d in days_ago]


def test_no_interactions_is_weak_and_active() -> None:
    r = compute(ScoreInputs(cadence_days=30), NOW)
    assert r.band == Band.weak and r.next_due_at is None
    assert r.components["recency"] == 0 and r.components["frequency"] == 0
    assert r.status == ContactStatus.needs_attention  # weak band always asks for attention


def test_recency_half_life_equals_cadence() -> None:
    r = compute(ScoreInputs(cadence_days=30, interactions=pts(30)), NOW)
    assert r.components["recency"] == pytest.approx(0.5, abs=1e-3)


def test_frequency_caps_at_one_and_a_half_times_expected() -> None:
    many = pts(*[i for i in range(1, 60)])
    r = compute(ScoreInputs(cadence_days=30, interactions=many), NOW)
    assert r.components["frequency"] == 1.0


def test_sentiment_maps_minus_one_to_zero_and_one_to_one() -> None:
    assert compute(ScoreInputs(30, pts(1, sentiment=-1.0)), NOW).components["sentiment"] == 0.0
    assert compute(ScoreInputs(30, pts(1, sentiment=1.0)), NOW).components["sentiment"] == 1.0
    assert compute(ScoreInputs(30, pts(1, sentiment=None)), NOW).components["sentiment"] == 0.5


def test_sentiment_uses_only_last_ten() -> None:
    old = [InteractionPoint(NOW - timedelta(days=50 + i), "mutual", -1.0) for i in range(5)]
    new = [InteractionPoint(NOW - timedelta(days=i), "mutual", 1.0) for i in range(10)]
    r = compute(ScoreInputs(30, old + new), NOW)
    assert r.components["sentiment"] == 1.0


def test_reciprocity_default_below_three_interactions() -> None:
    r = compute(ScoreInputs(30, pts(1, 2, direction="inbound")), NOW)
    assert r.components["reciprocity"] == 0.5


def test_reciprocity_balanced_is_one_and_one_sided_is_zero() -> None:
    balanced = pts(1, 2, direction="inbound") + pts(3, 4, direction="outbound")
    assert compute(ScoreInputs(30, balanced), NOW).components["reciprocity"] == 1.0
    one_sided = pts(1, 2, 3, 4, direction="outbound")
    assert compute(ScoreInputs(30, one_sided), NOW).components["reciprocity"] == 0.0
    mutual = pts(1, 2, 3, direction="mutual")
    assert compute(ScoreInputs(30, mutual), NOW).components["reciprocity"] == 1.0


@pytest.mark.parametrize(
    ("facts", "style", "expected"),
    [(0, False, 0.0), (5, False, 0.35), (10, False, 0.7), (15, False, 0.7), (0, True, 0.3), (10, True, 1.0)],
)
def test_depth(facts: int, style: bool, expected: float) -> None:
    r = compute(ScoreInputs(30, pts(1), active_facts=facts, communication_style_known=style), NOW)
    assert r.components["depth"] == pytest.approx(expected)


@pytest.mark.parametrize(
    ("delta", "overdue", "expected"),
    [
        (None, 0, 0.5),
        (0, 0, 0.5),
        (20, 0, 0.75),
        (40, 0, 0.75),
        (-10, 0, 0.375),
        (-20, 0, 0.25),
        (0, 1, 0.375),
        (0, 2, 0.25),
        (0, 5, 0.25),
        (20, 2, 0.5),
        (-20, 2, 0.0),
    ],
)
def test_momentum(delta: int | None, overdue: int, expected: float) -> None:
    prev = 50 if delta is not None else None
    ago = (50 - delta) if delta is not None else None
    r = compute(ScoreInputs(30, pts(1), overdue_tasks=overdue, previous_score=prev, score_30d_ago=ago), NOW)
    assert r.components["momentum"] == pytest.approx(expected)


@pytest.mark.parametrize(
    ("days", "cadence", "band"),
    [
        (60, 30, Band.weak),
        (61, 30, Band.drifting),
        (0.5, 14, Band.strong),
        (29, 14, Band.drifting),
    ],
)
def test_band_drifting_boundary(days: float, cadence: int, band: Band) -> None:
    ten = [InteractionPoint(NOW - timedelta(days=days + i * 0.01), "mutual", 1.0) for i in range(10)]
    r = compute(ScoreInputs(cadence, ten, active_facts=10, communication_style_known=True), NOW)
    if band == Band.drifting:
        assert r.band == Band.drifting
    else:
        assert r.band != Band.drifting


def test_strong_steady_weak_thresholds() -> None:
    strong = compute(ScoreInputs(30, pts(1, 2, 3, 4, sentiment=1.0), active_facts=10, communication_style_known=True), NOW)
    assert strong.score >= 70 and strong.band == Band.strong
    steady = compute(ScoreInputs(30, pts(20, sentiment=0.0)), NOW)
    assert 40 <= steady.score < 70 and steady.band == Band.steady
    weak = compute(ScoreInputs(30, pts(55, sentiment=-1.0)), NOW)
    assert weak.score < 40 and weak.band == Band.weak


def test_status_rules() -> None:
    fresh = compute(ScoreInputs(30, pts(1, 2, 3, sentiment=0.8), active_facts=6, communication_style_known=True), NOW)
    assert fresh.status == ContactStatus.active
    due = compute(
        ScoreInputs(30, pts(1, 2, 3, sentiment=0.8), active_facts=6, communication_style_known=True, tasks_due_within_3_days=1),
        NOW,
    )
    assert due.status == ContactStatus.follow_up
    cadence_passed = compute(ScoreInputs(14, pts(15, 16, 17, sentiment=1.0), active_facts=10, communication_style_known=True), NOW)
    assert cadence_passed.status == ContactStatus.follow_up
    dropped = compute(
        ScoreInputs(
            30,
            pts(1, 2, 3, sentiment=0.8),
            active_facts=6,
            communication_style_known=True,
            previous_score=80,
            score_30d_ago=95,
        ),
        NOW,
    )
    assert dropped.status == ContactStatus.needs_attention and dropped.delta_30d == -15
    archived = compute(ScoreInputs(30, pts(1), archived=True), NOW)
    assert archived.status == ContactStatus.archived


def test_next_due_is_earliest_of_task_and_cadence() -> None:
    task_due = NOW + timedelta(days=2)
    r = compute(ScoreInputs(30, pts(10), earliest_open_task_due=task_due), NOW)
    assert r.next_due_at == task_due
    r2 = compute(ScoreInputs(5, pts(10), earliest_open_task_due=task_due), NOW)
    assert r2.next_due_at == NOW - timedelta(days=5)  # cadence already passed
    assert compute(ScoreInputs(30, pts(10)), NOW).next_due_at == NOW + timedelta(days=20)


def test_score_is_bounded_and_integer() -> None:
    dense = [InteractionPoint(NOW - timedelta(days=i * 0.5), "inbound" if i % 2 else "outbound", 1.0) for i in range(180)]
    best = compute(ScoreInputs(1, dense, active_facts=10, communication_style_known=True, previous_score=90, score_30d_ago=50), NOW)
    assert best.score >= 95  # momentum tops out at 0.75, so 100 is not reachable by design
    worst = compute(ScoreInputs(30, pts(179, sentiment=-1.0), overdue_tasks=3, previous_score=10, score_30d_ago=60), NOW)
    assert 0 <= worst.score < 15


def test_weights_sum_to_one() -> None:
    from app.scoring.gravity import WEIGHTS

    assert sum(WEIGHTS.values()) == pytest.approx(1.0)
