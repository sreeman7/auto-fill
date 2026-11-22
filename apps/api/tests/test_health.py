import asyncio
import unittest

from httpx import ASGITransport, AsyncClient

from apps.api.app.main import app


class HealthTest(unittest.TestCase):
    def test_health(self) -> None:
        async def request() -> None:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/v1/health")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"status": "ok"})

        asyncio.run(request())
