from app.jobs.queue import BACKOFF_SECONDS


def test_backoff_schedule_matches_plan() -> None:
    assert BACKOFF_SECONDS == [30, 120, 600, 3600, 21600]
