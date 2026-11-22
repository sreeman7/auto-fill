import io
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from types import SimpleNamespace

from docx import Document
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.app.auth import AuthUser, get_current_user
from apps.api.app.database import get_db
from apps.api.app.main import app
from apps.api.app.models import Base, CareerFact, Profile
from apps.api.app.services.resume_parser import ResumeParseError, detect_file_type, extract_suggestions


def docx_bytes() -> bytes:
    document = Document()
    for line in ("Ada Lovelace", "ada@example.com", "+1 555 0123", "Education", "University of Alberta", "Skills", "Python"):
        document.add_paragraph(line)
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


class PhaseTwoTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.user = AuthUser(id=uuid4(), token="test-user", email="ada@example.com")

        def current_user() -> AuthUser:
            return self.user

        def database():
            with self.factory() as session:
                yield session

        app.dependency_overrides[get_current_user] = current_user
        app.dependency_overrides[get_db] = database
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()
        self.engine.dispose()

    async def test_profiles_are_private_and_validated(self) -> None:
        profile = {"fullName": "Ada Lovelace", "firstName": "Ada", "lastName": "Lovelace", "email": "ada@example.com", "phone": "+1 555 0123"}
        created = await self.client.put("/api/v1/profile", json=profile)
        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual((await self.client.get("/api/v1/profile")).json()["fullName"], "Ada Lovelace")
        rejected = await self.client.put("/api/v1/profile", json={**profile, "email": "invalid", "user_id": str(uuid4())})
        self.assertEqual(rejected.status_code, 422)
        owner = self.user
        self.user = AuthUser(id=uuid4(), token="other", email="other@example.com")
        self.assertEqual((await self.client.get("/api/v1/profile")).status_code, 404)
        self.user = owner
        self.assertEqual((await self.client.get("/api/v1/profile")).status_code, 200)

    async def test_upload_requires_valid_file_and_rejects_duplicate(self) -> None:
        with patch("apps.api.app.routes.resumes.MAX_RESUMES_PER_DAY", 0):
            limited = await self.client.post("/api/v1/resumes/upload", files={"file": ("resume.docx", b"any")})
        self.assertEqual(limited.status_code, 429)
        invalid = await self.client.post("/api/v1/resumes/upload", files={"file": ("fake.pdf", b"not a pdf", "application/pdf")})
        self.assertEqual(invalid.status_code, 422)
        with patch("apps.api.app.routes.resumes.MAX_UPLOAD_BYTES", 10):
            too_large = await self.client.post("/api/v1/resumes/upload", files={"file": ("large.pdf", b"X" * 11, "application/pdf")})
        self.assertEqual(too_large.status_code, 413)
        with patch("apps.api.app.routes.resumes.upload_resume", new_callable=AsyncMock) as storage:
            data = docx_bytes()
            first = await self.client.post("/api/v1/resumes/upload", files={"file": ("resume.docx", data, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
            self.assertEqual(first.status_code, 201, first.text)
            self.assertEqual(first.json()["status"], "pending_review")
            self.assertTrue(any(item["kind"] == "education" for item in first.json()["suggestions"]))
            self.assertEqual(storage.await_count, 1)
            duplicate = await self.client.post("/api/v1/resumes/upload", files={"file": ("resume.docx", data, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
            self.assertEqual(duplicate.status_code, 409)
            self.assertEqual(storage.await_count, 1)

    async def test_review_uses_user_selection_and_preserves_existing_profile(self) -> None:
        profile = {"fullName": "Ada Lovelace", "email": "ada@example.com", "phone": "My verified phone"}
        self.assertEqual((await self.client.put("/api/v1/profile", json=profile)).status_code, 200)
        with patch("apps.api.app.routes.resumes.upload_resume", new_callable=AsyncMock):
            response = await self.client.post("/api/v1/resumes/upload", files={"file": ("resume.docx", docx_bytes())})
        self.assertEqual(response.status_code, 201, response.text)
        resume = response.json()
        phone = next(item for item in resume["suggestions"] if item["kind"] == "phone")
        education = next(item for item in resume["suggestions"] if item["kind"] == "education")
        owner = self.user
        self.user = AuthUser(id=uuid4(), token="other", email="other@example.com")
        self.assertEqual((await self.client.get(f"/api/v1/resumes/{resume['id']}")).status_code, 404)
        self.assertEqual((await self.client.post(f"/api/v1/resumes/{resume['id']}/approve", json={"items": [{"id": phone["id"], "value": phone["proposed"]}]})).status_code, 404)
        self.user = owner
        approval = await self.client.post(f"/api/v1/resumes/{resume['id']}/approve", json={"items": [
            {"id": phone["id"], "value": phone["proposed"]},
            {"id": education["id"], "value": "University of Alberta, BSc"},
        ]})
        self.assertEqual(approval.status_code, 200, approval.text)
        self.assertEqual(approval.json()["approvedCount"], 2)
        self.assertEqual((await self.client.get("/api/v1/profile")).json()["phone"], "My verified phone")
        with self.factory() as db:
            facts = db.scalars(select(CareerFact).where(CareerFact.user_id == owner.id)).all()
            self.assertEqual(len(facts), 2)
            self.assertTrue(any(fact.edited_by_user and fact.source_excerpt == "University of Alberta" for fact in facts))
            self.assertEqual(db.get(Profile, owner.id).phone, "My verified phone")
        listed = (await self.client.get("/api/v1/facts")).json()
        self.assertEqual(len(listed), 2)
        fact_id = listed[0]["id"]
        self.user = AuthUser(id=uuid4(), token="other", email="other@example.com")
        self.assertEqual((await self.client.get("/api/v1/facts")).json(), [])
        self.assertEqual((await self.client.patch(f"/api/v1/facts/{fact_id}", json={"value": "stolen"})).status_code, 404)
        self.assertEqual((await self.client.delete(f"/api/v1/facts/{fact_id}")).status_code, 404)
        self.user = owner
        self.assertEqual((await self.client.patch(f"/api/v1/facts/{fact_id}", json={"value": "   "})).status_code, 422)
        updated = await self.client.patch(f"/api/v1/facts/{fact_id}", json={"value": "User corrected value"})
        self.assertEqual(updated.status_code, 200)
        self.assertTrue(updated.json()["editedByUser"])
        self.assertEqual((await self.client.delete(f"/api/v1/facts/{fact_id}")).status_code, 204)
        self.assertEqual(len((await self.client.get("/api/v1/facts")).json()), 1)
        self.assertEqual((await self.client.post(f"/api/v1/resumes/{resume['id']}/approve", json={"items": [{"id": phone["id"], "value": "again"}]})).status_code, 409)

    async def test_anonymous_private_route_is_rejected(self) -> None:
        app.dependency_overrides.clear()
        response = await self.client.get("/api/v1/profile")
        self.assertEqual(response.status_code, 401)

    async def test_account_deletion_requires_confirmation_and_removes_owned_data(self) -> None:
        await self.client.put("/api/v1/profile", json={"fullName": "Ada Lovelace", "email": "ada@example.com"})
        with patch("apps.api.app.routes.resumes.upload_resume", new_callable=AsyncMock):
            uploaded = await self.client.post("/api/v1/resumes/upload", files={"file": ("resume.docx", docx_bytes())})
        self.assertEqual(uploaded.status_code, 201)
        self.assertEqual((await self.client.delete("/api/v1/account")).status_code, 400)

        class FakeAdminClient:
            def __init__(self, *_args, **_kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

            async def delete(self, *_args, **_kwargs):
                return SimpleNamespace(status_code=204)

        fake_settings = SimpleNamespace(supabase_url="https://example.supabase.co", supabase_secret_key="server-only")
        with patch("apps.api.app.routes.account.settings", fake_settings), patch("apps.api.app.routes.account.remove_resume_strict", new_callable=AsyncMock) as storage, patch("apps.api.app.routes.account.httpx.AsyncClient", FakeAdminClient):
            response = await self.client.delete("/api/v1/account", headers={"X-Confirm-Delete": "delete-my-account"})
        self.assertEqual(response.status_code, 204, response.text)
        storage.assert_awaited_once()
        self.assertEqual((await self.client.get("/api/v1/profile")).status_code, 404)
        self.assertEqual((await self.client.get("/api/v1/resumes")).json(), [])


class ResumeParserTests(unittest.TestCase):
    def test_rejects_mismatched_and_malformed_documents(self) -> None:
        with self.assertRaises(ResumeParseError):
            detect_file_type("resume.pdf", b"PK not a PDF")
        with self.assertRaises(ResumeParseError):
            detect_file_type("resume.docx", b"PK not a ZIP")

    def test_extraction_keeps_source_excerpt(self) -> None:
        suggestions = extract_suggestions("Ada Lovelace\nEducation\nUniversity of Alberta\nSkills\nPython")
        education = next(item for item in suggestions if item.kind == "education")
        self.assertEqual(education.proposed, education.sourceExcerpt)


class AuthVerificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_verifies_identity_and_email_confirmation_with_auth_server(self) -> None:
        user_id = uuid4()

        class FakeClient:
            status_code = 200
            payload = {"id": str(user_id), "email": "ada@example.com", "email_confirmed_at": "2026-11-22T00:00:00Z"}

            def __init__(self, *_args, **_kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

            async def get(self, *_args, **_kwargs):
                return SimpleNamespace(status_code=self.status_code, json=lambda: self.payload)

        settings = SimpleNamespace(supabase_url="https://example.supabase.co", supabase_publishable_key="public")
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="test-token")
        with patch("apps.api.app.auth.settings", settings), patch("apps.api.app.auth.httpx.AsyncClient", FakeClient):
            user = await get_current_user(credentials)
            self.assertEqual(user.id, user_id)
            FakeClient.status_code = 401
            with self.assertRaises(HTTPException) as invalid:
                await get_current_user(credentials)
            self.assertEqual(invalid.exception.status_code, 401)
            FakeClient.status_code = 200
            FakeClient.payload = {"id": str(user_id), "email": "ada@example.com", "email_confirmed_at": None}
            with self.assertRaises(HTTPException) as unconfirmed:
                await get_current_user(credentials)
            self.assertEqual(unconfirmed.exception.status_code, 403)
