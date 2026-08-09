from collections.abc import Awaitable, Callable

import pytest
from httpx import ASGITransport, AsyncClient

from sentinel_api import main
from sentinel_api.settings import Settings

Check = Callable[[Settings], Awaitable[bool]]


@pytest.mark.parametrize(
    ("postgres_ok", "redis_ok", "expected_status"),
    [(True, True, 200), (False, True, 503), (True, False, 503), (False, False, 503)],
)
@pytest.mark.asyncio
async def test_readiness_reflects_dependency_state(
    monkeypatch: pytest.MonkeyPatch,
    postgres_ok: bool,
    redis_ok: bool,
    expected_status: int,
) -> None:
    async def fake_status(check: Check, settings: Settings) -> bool:
        del settings
        return postgres_ok if check is main.check_postgres else redis_ok

    monkeypatch.setattr(main, "dependency_status", fake_status)
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get("/ready")

    assert response.status_code == expected_status
    assert response.json()["dependencies"] == {
        "postgres": postgres_ok,
        "redis": redis_ok,
    }
