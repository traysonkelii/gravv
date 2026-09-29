from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_BASE = "https://gravv.app/problems/"
log = structlog.get_logger()


class Problem(Exception):
    """RFC 9457 Problem Details. `type_` is a short slug such as `not_a_member`."""

    def __init__(
        self,
        status: int,
        type_: str,
        title: str,
        detail: str | None = None,
        errors: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__(title)
        self.status = status
        self.type = type_
        self.title = title
        self.detail = detail
        self.errors = errors


def problem_response(
    request: Request,
    status: int,
    type_: str,
    title: str,
    detail: str | None = None,
    errors: list[dict[str, str]] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": PROBLEM_BASE + type_,
        "title": title,
        "status": status,
        "instance": request.url.path,
        "request_id": getattr(request.state, "request_id", None),
    }
    if detail:
        body["detail"] = detail
    if errors:
        body["errors"] = errors
    return JSONResponse(body, status_code=status, media_type="application/problem+json")


_HTTP_TITLES = {
    400: "Bad request",
    401: "Unauthenticated",
    403: "Forbidden",
    404: "Not found",
    405: "Method not allowed",
    409: "Conflict",
    413: "Payload too large",
    422: "Invalid request",
    429: "Too many requests",
}
_HTTP_TYPES = {
    400: "bad_request",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    422: "validation_error",
    429: "rate_limited",
}


# Postgres SQLSTATE -> Problem. RLS denials and security definer functions raise these.
_SQLSTATE = {
    "42501": (403, "forbidden", "Forbidden", "You do not have permission to do that."),
    "23505": (409, "conflict", "Already exists", "A record with the same key already exists."),
    "23503": (422, "invalid_reference", "Invalid reference", "A referenced record does not exist."),
    "23514": (422, "validation_error", "Invalid request", "A value is out of range."),
    "P0002": (404, "not_found", "Not found", None),
    "P0003": (409, "conflict", "Already used", None),
    "P0004": (410, "expired", "Expired", None),
}


def sqlstate(exc: DBAPIError) -> str | None:
    return getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DBAPIError)
    async def _dbapi(request: Request, exc: DBAPIError) -> JSONResponse:
        code = sqlstate(exc)
        mapped = _SQLSTATE.get(code or "")
        if mapped is None:
            log.exception("database_error", path=request.url.path, sqlstate=code)
            return problem_response(
                request,
                500,
                "internal_error",
                "Something went wrong",
                "The request could not be completed. Try again later.",
            )
        status, type_, title, detail = mapped
        message = str(getattr(exc.orig, "args", [""])[0] or "")
        if code and code.startswith("P0") and message:
            detail = message.split("\n")[0]
        return problem_response(request, status, type_, title, detail)

    @app.exception_handler(Problem)
    async def _problem(request: Request, exc: Problem) -> JSONResponse:
        return problem_response(request, exc.status, exc.type, exc.title, exc.detail, exc.errors)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": str(e["msg"])} for e in exc.errors()
        ]
        return problem_response(
            request, 422, "validation_error", "Invalid request", "One or more fields are invalid.", errors
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else None
        return problem_response(
            request,
            exc.status_code,
            _HTTP_TYPES.get(exc.status_code, "error"),
            _HTTP_TITLES.get(exc.status_code, "Error"),
            detail,
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled", path=request.url.path)
        return problem_response(
            request,
            500,
            "internal_error",
            "Something went wrong",
            "The request could not be completed. Try again, and contact support with the request id if it persists.",
        )
