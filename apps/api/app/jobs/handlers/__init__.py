"""Job handlers registered by kind. Each handler is idempotent: re-running after a crash must not duplicate rows."""

from collections.abc import Awaitable, Callable
from typing import Any

from app.jobs.queue import Job

Handler = Callable[[Job], Awaitable[dict[str, Any] | None]]
HANDLERS: dict[str, Handler] = {}


def handler(kind: str) -> Callable[[Handler], Handler]:
    def register(fn: Handler) -> Handler:
        HANDLERS[kind] = fn
        return fn

    return register


@handler("noop")
async def noop(job: Job) -> dict[str, Any]:
    return {"echo": job.payload}


# Register handler modules (import side effects).
from app.jobs.handlers import capture as _capture  # noqa: E402, F401
from app.jobs.handlers import portability as _portability  # noqa: E402, F401
from app.jobs.handlers import profile as _profile  # noqa: E402, F401
from app.jobs.handlers import scoring as _scoring  # noqa: E402, F401
