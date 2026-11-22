"""Phase 7 API safeguards without live credentials."""

import json
import unittest
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient

from apps.api.app.config import Settings
from apps.api.app.main import app
from apps.api.app.security import RateLimiter


class SecurityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_private_api_does_not_expose_secrets_or_query_in_logs(self):
        with self.assertLogs("auto_fill.api", level="INFO") as logs:
            response = await self.client.get("/api/v1/applications?q=private%20salary", headers={"Authorization": "Bearer secret-token"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
        self.assertIn("default-src 'none'", response.headers["Content-Security-Policy"])
        self.assertEqual(len(response.headers["X-Request-ID"]), 32)
        record = json.loads(logs.records[0].getMessage())
        self.assertEqual(record["route"], "/api/v1/applications")
        self.assertEqual(record["status"], 503)
        self.assertNotIn("private", logs.output[0])
        self.assertNotIn("secret-token", logs.output[0])

    async def test_rate_limited_response_has_retry_after(self):
        with patch("apps.api.app.security.limiter") as limiter:
            limiter.check.return_value = 7
            response = await self.client.get("/api/v1/applications")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["Retry-After"], "7")
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    async def test_readiness_requires_a_database(self):
        with patch("apps.api.app.main.database_ready", return_value=False):
            response = await self.client.get("/api/v1/ready")
        self.assertEqual(response.status_code, 503)
        with patch("apps.api.app.main.database_ready", return_value=True):
            response = await self.client.get("/api/v1/ready")
        self.assertEqual(response.json(), {"status": "ready"})

    async def test_api_docs_keep_their_browser_assets(self):
        response = await self.client.get("/docs")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Content-Security-Policy", response.headers)

    def test_bounded_limiter_and_hosted_settings(self):
        limiter = RateLimiter(max_keys=2)
        self.assertEqual(limiter.check(("a", "all"), 1), 0)
        self.assertGreater(limiter.check(("a", "all"), 1), 0)
        limiter.check(("b", "all"), 1)
        limiter.check(("c", "all"), 1)
        self.assertEqual(len(limiter.buckets), 2)
        kwargs = dict(app_env="staging", supabase_url="https://example.supabase.co",
                      supabase_publishable_key="public", supabase_secret_key="server-secret",
                      database_url="postgresql+psycopg://u:p@db.example/postgres?sslmode=require",
                      tailor_signing_key="a" * 32, allowed_origins=("chrome-extension://abc",))
        Settings(**kwargs)
        with self.assertRaises(ValueError):
            Settings(**{**kwargs, "database_url": "postgresql+psycopg://u:p@db.example/postgres"})
        with self.assertRaises(ValueError):
            Settings(**{**kwargs, "allowed_origins": ("*",)})
        with self.assertRaises(ValueError):
            Settings(**{**kwargs, "supabase_url": "http://example.supabase.co"})
