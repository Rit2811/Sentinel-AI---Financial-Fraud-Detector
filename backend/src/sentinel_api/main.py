import asyncio
from collections.abc import Awaitable, Callable
from typing import cast

import asyncpg
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from sentinel_api.settings import Settings, get_settings

app = FastAPI(title="Sentinel AI API", version="0.1.0", docs_url=None, redoc_url=None)


async def check_postgres(settings: Settings) -> bool:
    connection = await asyncio.wait_for(
        asyncpg.connect(settings.postgres_url), timeout=settings.readiness_timeout_seconds
    )
    try:
        value = await connection.fetchval("SELECT 1")
        return cast(int, value) == 1
    finally:
        await connection.close(timeout=settings.readiness_timeout_seconds)


async def check_redis(settings: Settings) -> bool:
    client = Redis.from_url(
        settings.redis_url,
        socket_connect_timeout=settings.readiness_timeout_seconds,
        socket_timeout=settings.readiness_timeout_seconds,
    )
    try:
        return bool(await client.ping())
    finally:
        await client.aclose()


async def dependency_status(
    check: Callable[[Settings], Awaitable[bool]], settings: Settings
) -> bool:
    try:
        return await check(settings)
    except (TimeoutError, OSError, asyncpg.PostgresError):
        return False
    except Exception:
        return False


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "sentinel-ai-api"}


@app.get("/ready")
async def ready() -> JSONResponse:
    settings = get_settings()
    postgres_ok, redis_ok = await asyncio.gather(
        dependency_status(check_postgres, settings),
        dependency_status(check_redis, settings),
    )
    ready_now = postgres_ok and redis_ok
    return JSONResponse(
        status_code=200 if ready_now else 503,
        content={
            "status": "ready" if ready_now else "not_ready",
            "dependencies": {"postgres": postgres_ok, "redis": redis_ok},
        },
    )
