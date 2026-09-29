"""Tiny HTTP responder on port 8080 for the worker's App Runner health check (Section 13.2). No dependencies."""

import asyncio
import contextlib

import structlog

log = structlog.get_logger()


async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    with contextlib.suppress(Exception):
        await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=5)
    body = b'{"status":"ok"}'
    writer.write(
        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "
        + str(len(body)).encode()
        + b"\r\nConnection: close\r\n\r\n"
        + body
    )
    await writer.drain()
    writer.close()


async def serve(port: int = 8080) -> asyncio.AbstractServer | None:
    try:
        server = await asyncio.start_server(_handle, "0.0.0.0", port)
    except OSError as exc:
        log.warning("worker_health_unavailable", port=port, error=str(exc))
        return None
    log.info("worker_health_listening", port=port)
    return server
