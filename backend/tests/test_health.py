import pytest
from httpx import ASGITransport, AsyncClient

from sentinel_api.main import app


@pytest.mark.asyncio
async def test_health_reports_process_liveness() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "sentinel-ai-api"}
