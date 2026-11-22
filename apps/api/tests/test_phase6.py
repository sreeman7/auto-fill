"""Phase 6 tracker behavior and owner boundaries."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.app.auth import AuthUser, get_current_user
from apps.api.app.database import get_db
from apps.api.app.main import app
from apps.api.app.models import Application, Base
from apps.api.app.services.application_tracking import canonical_job_url


class PhaseSixTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.owner = AuthUser(id=uuid4(), token="owner", email="owner@example.com")
        self.user = self.owner

        def current_user():
            return self.user

        def database():
            with self.factory() as db:
                yield db

        app.dependency_overrides[get_current_user] = current_user
        app.dependency_overrides[get_db] = database
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        app.dependency_overrides.clear()
        self.engine.dispose()

    def payload(self, **changes):
        return {"company": "Acme", "jobTitle": "Engineer", "jobUrl": "https://jobs.example/role/42?gh_jid=42&utm_source=email",
                "location": "Edmonton", "resumeVersion": "resume-v2", "notes": "Ask about team", "interviewDates": [],
                "followUpDates": [], **changes}

    async def create(self, **changes):
        return await self.client.post("/api/v1/applications", json=self.payload(**changes))

    async def test_create_saved_and_duplicate_url(self):
        first = await self.create()
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(first.json()["status"], "saved")
        self.assertIsNone(first.json()["appliedOn"])
        duplicate = await self.create(jobUrl="https://JOBS.EXAMPLE/role/42/?gh_jid=42&fbclid=abc#details")
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.json()["detail"]["code"], "duplicate_url")
        self.assertEqual(canonical_job_url("https://jobs.example/role/42?gh_jid=42&utm_source=ad"),
                         "https://jobs.example/role/42?gh_jid=42")
        self.assertNotEqual(canonical_job_url("https://jobs.example/role/42?gh_jid=43"),
                            "https://jobs.example/role/42?gh_jid=42")

    async def test_possible_duplicate_requires_override_and_exact_never_allows_override(self):
        self.assertEqual((await self.create()).status_code, 201)
        possible = await self.create(company=" ACME ", jobTitle="engineer", jobUrl="https://jobs.example/role/43")
        self.assertEqual(possible.status_code, 409)
        self.assertEqual(possible.json()["detail"]["code"], "possible_duplicate")
        allowed = await self.create(jobUrl="https://jobs.example/role/43", allowPossibleDuplicate=True)
        self.assertEqual(allowed.status_code, 201)
        exact = await self.create(allowPossibleDuplicate=True)
        self.assertEqual(exact.status_code, 409)
        self.assertEqual(exact.json()["detail"]["code"], "duplicate_url")

    async def test_manual_submission_confirmation_and_dates(self):
        item = (await self.create()).json()
        endpoint = f"/api/v1/applications/{item['id']}"
        request = self.payload(status="applied", appliedOn="2025-10-01", interviewDates=["2025-10-10"], followUpDates=["2025-10-12"])
        self.assertEqual((await self.client.put(endpoint, json=request)).status_code, 422)
        confirmed = await self.client.put(endpoint, json={**request, "confirmSubmitted": True})
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        self.assertEqual(confirmed.json()["appliedOn"], "2025-10-01")
        self.assertEqual(confirmed.json()["interviewDates"], ["2025-10-10"])
        progressed = await self.client.put(endpoint, json={**request, "status": "interview"})
        self.assertEqual(progressed.status_code, 200, progressed.text)
        self.assertEqual((await self.client.put(endpoint, json={**request, "status": "saved"})).status_code, 422)
        reverted = await self.client.put(endpoint, json={**request, "status": "ready_for_review", "appliedOn": None})
        self.assertEqual(reverted.status_code, 200, reverted.text)
        self.assertIsNone(reverted.json()["appliedOn"])
        self.assertEqual((await self.client.put(endpoint, json=request)).status_code, 422)

    async def test_search_filter_sort_update_delete_and_owner_scope(self):
        first = (await self.create()).json()
        second = (await self.create(company="Beta", jobTitle="Designer", jobUrl="https://jobs.example/role/77", notes="Remote work")).json()
        rows = (await self.client.get("/api/v1/applications", params={"q": "remote"})).json()
        self.assertEqual(rows["total"], 1)
        self.assertEqual(rows["items"][0]["id"], second["id"])
        ordered = (await self.client.get("/api/v1/applications", params={"sort": "company_asc", "limit": 1, "offset": 1})).json()
        self.assertEqual(ordered["total"], 2)
        self.assertEqual(ordered["items"][0]["id"], second["id"])
        update = await self.client.put(f"/api/v1/applications/{first['id']}", json=self.payload(status="in_progress"))
        self.assertEqual(update.status_code, 200, update.text)
        filtered = (await self.client.get("/api/v1/applications", params={"status": "in_progress"})).json()
        self.assertEqual(filtered["total"], 1)
        self.user = AuthUser(id=uuid4(), token="other", email="other@example.com")
        self.assertEqual((await self.client.get("/api/v1/applications")).json()["total"], 0)
        self.assertEqual((await self.client.get(f"/api/v1/applications/{first['id']}")).status_code, 404)
        self.assertEqual((await self.client.delete(f"/api/v1/applications/{first['id']}")).status_code, 404)
        self.user = self.owner
        self.assertEqual((await self.client.delete(f"/api/v1/applications/{first['id']}")).status_code, 204)
        self.assertEqual((await self.client.get("/api/v1/applications")).json()["total"], 1)

    async def test_validation_and_account_deletion(self):
        self.assertEqual((await self.create(jobUrl="javascript:alert(1)")).status_code, 422)
        self.assertEqual((await self.create(jobUrl="https://jobs.example/a\n/b")).status_code, 422)
        self.assertEqual((await self.create(interviewDates=["2025-10-10", "2025-10-10"])).status_code, 422)
        self.assertEqual((await self.create()).status_code, 201)

        class FakeAdminClient:
            def __init__(self, *_args, **_kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *_args): return False
            async def delete(self, *_args, **_kwargs): return SimpleNamespace(status_code=204)

        with patch("apps.api.app.routes.account.settings", SimpleNamespace(supabase_secret_key="server-only", supabase_url="https://example.supabase.co")), \
             patch("apps.api.app.routes.account.remove_resume_strict", new_callable=AsyncMock), \
             patch("apps.api.app.routes.account.httpx.AsyncClient", FakeAdminClient):
            response = await self.client.delete("/api/v1/account", headers={"X-Confirm-Delete": "delete-my-account"})
        self.assertEqual(response.status_code, 204, response.text)
        with self.factory() as db:
            self.assertIsNone(db.scalar(select(Application)))
