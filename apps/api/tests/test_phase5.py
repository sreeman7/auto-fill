import json as json_lib
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.pool import StaticPool

from apps.api.app.auth import AuthUser, get_current_user
from apps.api.app.database import get_db
from apps.api.app.main import app
from apps.api.app.models import ApprovedAnswer, Base, CareerFact, Resume, ScreeningDraft
from apps.api.app.services.screening import (
    InterpretationResult, ModelInterpretation, compose_answer, interpret_with_model, sensitive_reason,
)


QUESTION = "Describe a project that shows your Python experience."
JOB_CONTEXT = "This engineering role involves Python data pipelines."


class PhaseFiveTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.user = AuthUser(id=uuid4(), token="owner", email="ada@example.com")
        self.owner_id = self.user.id
        self.fact_id = uuid4()
        resume_id = uuid4()
        with self.factory() as db:
            db.add(Resume(id=resume_id, user_id=self.owner_id, original_filename="resume.pdf", content_type="application/pdf",
                          byte_count=100, sha256="f" * 64, storage_path=f"{self.owner_id}/{resume_id}.pdf", status="approved", suggestions=[]))
            db.add(CareerFact(id=self.fact_id, user_id=self.owner_id, source_resume_id=resume_id, kind="project",
                              value="Built Python data pipeline", source_excerpt="Built Python data pipeline"))
            db.commit()

        def current_user():
            return self.user

        def database():
            with self.factory() as db:
                yield db

        app.dependency_overrides[get_current_user] = current_user
        app.dependency_overrides[get_db] = database
        self.settings_patch = patch("apps.api.app.routes.screening.settings", SimpleNamespace(tailor_signing_key="long-random-test-secret-for-screening-123456", openai_model="test-model"))
        self.settings_patch.start()
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.settings_patch.stop()
        app.dependency_overrides.clear()
        self.engine.dispose()

    def result(self, *, sensitive=False, intent="project", fact_ids=None, job_quote="Python data pipelines"):
        return InterpretationResult(ModelInterpretation(intent=intent, sensitive=sensitive,
            factIds=[self.fact_id] if fact_ids is None else fact_ids, jobQuote=job_quote), 100, 20)

    async def draft(self, result=None, question=QUESTION, max_words=120):
        with patch("apps.api.app.routes.screening.interpret_with_model", new_callable=AsyncMock, return_value=result or self.result()):
            return await self.client.post("/api/v1/screening/draft", json={"question": question, "jobContext": JOB_CONTEXT, "maxWords": max_words})

    async def test_sensitive_questions_do_not_reach_model_or_persist(self):
        questions = ["Are you authorized to work in Canada?", "Will you require visa sponsorship?",
                     "Do you have a disability?", "What is your race or ethnicity?", "What is your gender identity?",
                     "Are you a veteran?", "Do you have a criminal conviction?", "Do you hold a security clearance?",
                     "Can you work in the United States?", "Are you a U.S. citizen?"]
        with patch("apps.api.app.routes.screening.interpret_with_model", new_callable=AsyncMock) as model:
            for question in questions:
                response = await self.client.post("/api/v1/screening/draft", json={"question": question})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertTrue(response.json()["sensitive"])
                self.assertNotIn("draftId", response.json())
            model.assert_not_awaited()
        with self.factory() as db:
            self.assertIsNone(db.scalar(select(ScreeningDraft)))

    async def test_draft_is_assembled_from_approved_fact_and_saved_only_after_confirmation(self):
        response = await self.draft()
        self.assertEqual(response.status_code, 200, response.text)
        proposal = response.json()
        self.assertFalse(proposal["sensitive"])
        self.assertEqual(proposal["answer"], "A few relevant details from my background: Built Python data pipeline.")
        self.assertEqual(proposal["sourceFacts"][0]["value"], "Built Python data pipeline")
        self.assertEqual(proposal["inputTokens"], 100)
        endpoint = f"/api/v1/screening/{proposal['draftId']}/approve"
        self.assertEqual((await self.client.post(endpoint, json={"answer": proposal["answer"]})).status_code, 422)
        self.assertEqual((await self.client.get("/api/v1/screening/answers")).json(), [])
        saved = await self.client.post(endpoint, json={"answer": proposal["answer"], "confirmed": True})
        self.assertEqual(saved.status_code, 201, saved.text)
        self.assertFalse(saved.json()["editedByUser"])
        self.assertEqual(saved.json()["sourceFactIds"], [str(self.fact_id)])
        self.assertEqual((await self.client.post(endpoint, json={"answer": proposal["answer"], "confirmed": True})).status_code, 409)
        self.assertEqual(len((await self.client.get("/api/v1/screening/answers")).json()), 1)
        self.assertEqual((await self.client.delete(f"/api/v1/screening/answers/{saved.json()['id']}")).status_code, 204)
        self.assertEqual((await self.client.get("/api/v1/screening/answers")).json(), [])

    async def test_personal_motivation_requires_user_text_and_marks_edit(self):
        response = await self.draft(self.result(intent="motivation"), question="Why are you interested in this role?")
        self.assertEqual(response.status_code, 200, response.text)
        proposal = response.json()
        self.assertEqual(proposal["answer"], "")
        self.assertTrue(proposal["needsPersonalInput"])
        saved = await self.client.post(f"/api/v1/screening/{proposal['draftId']}/approve", json={
            "answer": "I am interested in the team and its work.", "confirmed": True,
        })
        self.assertEqual(saved.status_code, 201, saved.text)
        self.assertTrue(saved.json()["editedByUser"])
        self.assertEqual(saved.json()["sourceFactIds"], [])

    async def test_model_sensitive_flag_and_invalid_fact_or_job_quote(self):
        sensitive = await self.draft(self.result(sensitive=True))
        self.assertEqual(sensitive.status_code, 200)
        self.assertTrue(sensitive.json()["sensitive"])
        self.assertEqual((await self.draft(self.result(fact_ids=[uuid4()]))).status_code, 503)
        self.assertEqual((await self.draft(self.result(job_quote="Kubernetes"))).status_code, 503)
        with self.factory() as db:
            self.assertIsNone(db.scalar(select(ScreeningDraft)))

    async def test_owner_stale_fact_and_tamper_checks(self):
        proposal = (await self.draft()).json()
        endpoint = f"/api/v1/screening/{proposal['draftId']}/approve"
        self.user = AuthUser(id=uuid4(), token="other", email="other@example.com")
        self.assertEqual((await self.client.post(endpoint, json={"answer": "stolen", "confirmed": True})).status_code, 404)
        self.assertEqual((await self.client.get("/api/v1/screening/answers")).json(), [])
        self.user = AuthUser(id=self.owner_id, token="owner", email="ada@example.com")
        with self.factory() as db:
            draft = db.get(ScreeningDraft, UUID(proposal["draftId"]))
            draft.payload["answer"] = "Invented credential"
            flag_modified(draft, "payload")
            db.commit()
        self.assertEqual((await self.client.post(endpoint, json={"answer": "Invented credential", "confirmed": True})).status_code, 409)
        fresh = (await self.draft()).json()
        with self.factory() as db:
            fact = db.get(CareerFact, self.fact_id)
            fact.value = "Changed approved fact"
            db.commit()
        self.assertEqual((await self.client.post(f"/api/v1/screening/{fresh['draftId']}/approve", json={"answer": fresh["answer"], "confirmed": True})).status_code, 409)

    async def test_tampered_saved_answer_is_not_returned(self):
        proposal = (await self.draft()).json()
        saved = (await self.client.post(f"/api/v1/screening/{proposal['draftId']}/approve", json={"answer": proposal["answer"], "confirmed": True})).json()
        with self.factory() as db:
            answer = db.get(ApprovedAnswer, UUID(saved["id"]))
            answer.answer = "Fabricated credential"
            db.commit()
        self.assertEqual((await self.client.get("/api/v1/screening/answers")).status_code, 409)

    async def test_account_deletion_removes_screening_data(self):
        proposal = (await self.draft()).json()
        saved = await self.client.post(f"/api/v1/screening/{proposal['draftId']}/approve", json={"answer": proposal["answer"], "confirmed": True})
        self.assertEqual(saved.status_code, 201)

        class FakeAdminClient:
            def __init__(self, *_args, **_kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

            async def delete(self, *_args, **_kwargs):
                return SimpleNamespace(status_code=204)

        with patch("apps.api.app.routes.account.settings", SimpleNamespace(supabase_secret_key="server-only", supabase_url="https://example.supabase.co")), \
             patch("apps.api.app.routes.account.remove_resume_strict", new_callable=AsyncMock), \
             patch("apps.api.app.routes.account.httpx.AsyncClient", FakeAdminClient):
            response = await self.client.delete("/api/v1/account", headers={"X-Confirm-Delete": "delete-my-account"})
        self.assertEqual(response.status_code, 204, response.text)
        with self.factory() as db:
            self.assertIsNone(db.scalar(select(ScreeningDraft)))
            self.assertIsNone(db.scalar(select(ApprovedAnswer)))


class ScreeningServiceTests(unittest.IsolatedAsyncioTestCase):
    def test_sensitive_classifier_and_word_limit(self):
        self.assertEqual(sensitive_reason("Are you legally permitted to work?"), "work authorization")
        self.assertIsNone(sensitive_reason(QUESTION))
        self.assertIsNone(sensitive_reason("Can you work with Python?"))
        fact = SimpleNamespace(id=uuid4(), kind="project", value="Built Python data pipeline")
        result = InterpretationResult(ModelInterpretation(intent="project", sensitive=False, factIds=[fact.id], jobQuote=""), 0, 0)
        self.assertTrue(compose_answer(QUESTION, "", 60, result, [fact])["answer"])
        self.assertTrue(compose_answer(QUESTION, "", 5, result, [fact])["needsPersonalInput"])

    async def test_model_request_is_structured_and_does_not_store_response(self):
        fact = SimpleNamespace(id=uuid4(), kind="project", value="Built Python data pipeline")

        class FakeClient:
            request = None

            def __init__(self, *_args, **_kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

            async def post(self, _url, json, headers):
                FakeClient.request = json
                FakeClient.headers = headers
                output = {"intent": "project", "sensitive": False, "factIds": [str(fact.id)], "jobQuote": ""}
                return SimpleNamespace(status_code=200, json=lambda: {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": json_lib.dumps(output)}]}], "usage": {"input_tokens": 42, "output_tokens": 12}})

        with patch("apps.api.app.services.screening.settings", SimpleNamespace(openai_api_key="server-key", openai_model="test-model")), \
             patch("apps.api.app.services.screening.httpx.AsyncClient", FakeClient):
            result = await interpret_with_model(QUESTION, JOB_CONTEXT, [fact])
        self.assertEqual(result.input_tokens, 42)
        self.assertEqual(result.output_tokens, 12)
        self.assertFalse(FakeClient.request["store"])
        self.assertTrue(FakeClient.request["text"]["format"]["strict"])
        self.assertEqual(FakeClient.headers["Authorization"], "Bearer server-key")
