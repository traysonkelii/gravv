"""Lambda entrypoints (D-039): the API through Mangum behind a function URL, the worker as a scheduled drain.
Both run from the API image with `python -m awslambdaric app.lambda_handlers.<name>`."""

import asyncio
from typing import Any

from mangum import Mangum

from app.main import app
from app.worker import drain

# One loop for the life of the container so the cached async engines stay bound to it across invocations.
_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)

api = Mangum(app, lifespan="off")


def worker(event: dict[str, Any], context: Any) -> dict[str, int]:
    budget = context.get_remaining_time_in_millis() / 1000 - 20
    return {"jobs_run": _loop.run_until_complete(drain(max(budget, 5.0)))}
