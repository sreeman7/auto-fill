import asyncio
import unittest

from httpx import ASGITransport, AsyncClient

from apps.api.app.main import app


class HealthTest(unittest.TestCase):
    def test_only_active_product_routes_are_exposed(self) -> None:
        paths = set(app.openapi()["paths"])
        self.assertTrue({"/api/v1/profile", "/api/v1/resumes", "/api/v1/applications"} <= paths)
        self.assertFalse(any(path.startswith(("/api/v1/tailor", "/api/v1/screening")) for path in paths))

    def test_health(self) -> None:
        async def request() -> None:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/v1/health")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"status": "ok"})

        asyncio.run(request())
