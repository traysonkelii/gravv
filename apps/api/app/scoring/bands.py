"""Band derivation shared by the API read models and the scoring engine (Section 7.9)."""

from datetime import UTC, datetime

from app.db.enums import Band

# SQL twin of band_for(); keep the two in sync.
BAND_SQL = (
    "case when {t}.last_interaction_at is not null "
    "and {t}.last_interaction_at < now() - ({t}.cadence_days * 2) * interval '1 day' then 'drifting' "
    "when {t}.gravity_score >= 70 then 'strong' when {t}.gravity_score >= 40 then 'steady' else 'weak' end"
)


def band_for(score: int, last_interaction_at: datetime | None, cadence_days: int, now: datetime | None = None) -> Band:
    now = now or datetime.now(UTC)
    if last_interaction_at is not None and (now - last_interaction_at).days > 2 * cadence_days:
        return Band.drifting
    if score >= 70:
        return Band.strong
    if score >= 40:
        return Band.steady
    return Band.weak
