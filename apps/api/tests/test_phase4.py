import io
import json as json_lib
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

from docx import Document
from httpx import ASGITransport, AsyncClient
from pypdf import PdfReader
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.app.auth import AuthUser, get_current_user
from apps.api.app.database import get_db
from apps.api.app.main import app
from apps.api.app.models import Base, CareerFact, Profile, Resume, TailoringDraft
from apps.api.app.services.tailoring import ModelAnalysis, ModelResult, TailoringError, analyze_with_model, build_grounded_analysis, supported_rewrite


def sample_docx() -> bytes:
    document = Document()
    document.add_paragraph("Ada Lovelace")
    document.add_paragraph("Built Python data pipeline")
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


JOB = "Example Labs seeks a Data Engineer. Required: Python data pipeline. Preferred: AWS cloud deployment. Build reliable data systems with the engineering team."


def model_result(after: str = "Built data pipeline in Python") -> ModelResult:
    return ModelResult(ModelAnalysis(jobTitle="Data Engineer", company="Example Labs", requirements=[
        {"quote": "Python data pipeline", "priority": "required"},
        {"quote": "AWS cloud deployment", "priority": "preferred"},
    ], suggestions=[{"factId": FACT_ID, "after": after}]), 300, 80)


FACT_ID = uuid4()


class PhaseFourTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.user = AuthUser(id=uuid4(), token="owner", email="ada@example.com")
        self.owner_id = self.user.id
        self.settings_patch = patch("apps.api.app.routes.tailor.settings", SimpleNamespace(tailor_signing_key="test-secret-longer-than-thirty-two-characters", openai_model="test-model"))
        self.settings_patch.start()
        self.resume_id = uuid4()
        with self.factory() as db:
            db.add(Profile(user_id=self.user.id, full_name="Ada Lovelace", email="ada@example.com"))
            db.add(Resume(id=self.resume_id, user_id=self.user.id, original_filename="resume.docx", content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                          byte_count=100, sha256="a" * 64, storage_path=f"{self.user.id}/{self.resume_id}.docx", status="approved", suggestions=[]))
            db.add(CareerFact(id=FACT_ID, user_id=self.user.id, source_resume_id=self.resume_id, kind="experience", value="Built Python data pipeline", source_excerpt="Built Python data pipeline"))
            db.commit()

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
        self.settings_patch.stop()

    async def analyze(self, result=None):
        with patch("apps.api.app.routes.tailor.download_resume", new_callable=AsyncMock, return_value=sample_docx()), \
             patch("apps.api.app.routes.tailor.analyze_with_model", new_callable=AsyncMock, return_value=result or model_result()):
            return await self.client.post("/api/v1/tailor/analyze", json={"resumeId": str(self.resume_id), "jobDescription": JOB})

    async def test_analysis_is_grounded_and_export_uses_selected_changes(self):
        response = await self.analyze()
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["score"], 67)
        self.assertEqual(data["requirements"][0]["evidenced"], True)
        self.assertEqual(data["requirements"][0]["evidence"][0]["value"], "Built Python data pipeline")
        self.assertEqual(data["requirements"][1]["evidenced"], False)
        self.assertEqual(data["inputTokens"], 300)
        self.assertIn("Built Python data pipeline", data["originalText"])
        self.assertEqual(data["suggestions"][0]["before"], "Built Python data pipeline")
        draft_id = data["draftId"]
        suggestion_id = data["suggestions"][0]["id"]
        selected = await self.client.post(f"/api/v1/tailor/{draft_id}/export", json={"selectedSuggestionIds": [suggestion_id]})
        self.assertEqual(selected.status_code, 200, selected.text[:100])
        self.assertEqual(selected.headers["content-type"], "application/pdf")
        selected_text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(selected.content)).pages)
        self.assertIn("Built data pipeline in Python", selected_text)
        self.assertNotIn("Built Python data pipeline", selected_text)
        unchanged = await self.client.post(f"/api/v1/tailor/{draft_id}/export", json={"selectedSuggestionIds": []})
        self.assertEqual(unchanged.status_code, 200)
        original_text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(unchanged.content)).pages)
        self.assertIn("Built Python data pipeline", original_text)

    async def test_rejects_other_user_unknown_selection_and_stale_fact(self):
        data = (await self.analyze()).json()
        endpoint = f"/api/v1/tailor/{data['draftId']}/export"
        self.user = AuthUser(id=uuid4(), token="other", email="other@example.com")
        self.assertEqual((await self.client.post(endpoint, json={"selectedSuggestionIds": []})).status_code, 404)
        self.assertEqual((await self.client.post("/api/v1/tailor/analyze", json={"resumeId": str(self.resume_id), "jobDescription": JOB})).status_code, 404)
        self.user = AuthUser(id=self.owner_id, token="owner", email="ada@example.com")
        self.assertEqual((await self.client.post(endpoint, json={"selectedSuggestionIds": [str(uuid4())]})).status_code, 422)
        with self.factory() as db:
            fact = db.get(CareerFact, FACT_ID)
            fact.value = "Changed approved fact"
            db.commit()
        self.assertEqual((await self.client.post(endpoint, json={"selectedSuggestionIds": []})).status_code, 409)

    async def test_rejects_tampered_draft(self):
        data = (await self.analyze()).json()
        with self.factory() as db:
            draft = db.get(TailoringDraft, UUID(data["draftId"]))
            draft.payload["suggestions"][0]["after"] = "Invented employer and certification"
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(draft, "payload")
            db.commit()
        response = await self.client.post(f"/api/v1/tailor/{data['draftId']}/export", json={"selectedSuggestionIds": []})
        self.assertEqual(response.status_code, 409)
        self.assertIn("draft was changed", response.json()["detail"])

    async def test_rejects_hallucinated_model_output_and_invalid_request(self):
        self.assertEqual((await self.client.post("/api/v1/tailor/analyze", json={"resumeId": str(self.resume_id), "jobDescription": "short"})).status_code, 422)
        response = await self.analyze(model_result("Built Python AWS cloud pipeline"))
        self.assertEqual(response.status_code, 503)
        self.assertIn("unsupported resume content", response.json()["detail"])
        with self.factory() as db:
            self.assertEqual(db.scalar(select(TailoringDraft)), None)

    def test_requirement_quote_and_fact_reference_must_be_real(self):
        fact = SimpleNamespace(id=FACT_ID, kind="experience", value="Built Python data pipeline")
        bad_quote = ModelResult(ModelAnalysis(jobTitle="", company="", requirements=[{"quote": "Kubernetes", "priority": "required"}], suggestions=[]), 0, 0)
        with self.assertRaises(TailoringError):
            build_grounded_analysis(JOB, bad_quote, [fact])
        bad_fact = ModelResult(ModelAnalysis(jobTitle="", company="", requirements=[], suggestions=[{"factId": uuid4(), "after": "Built Python pipeline"}]), 0, 0)
        with self.assertRaises(TailoringError):
            build_grounded_analysis(JOB, bad_fact, [fact])
        self.assertFalse(supported_rewrite("Built Python pipeline", "Python Python Python pipeline"))
        self.assertFalse(supported_rewrite("Not certified in AWS", "Certified in AWS"))


class ModelClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_structured_request_disables_storage_and_counts_tokens(self):
        expected = model_result().analysis.model_dump(mode="json")

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
                return SimpleNamespace(status_code=200, json=lambda: {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": json_lib.dumps(expected)}]}], "usage": {"input_tokens": 300, "output_tokens": 80}})

        with patch("apps.api.app.services.tailoring.settings", SimpleNamespace(openai_api_key="server-secret", openai_model="test-model")), \
             patch("apps.api.app.services.tailoring.httpx.AsyncClient", FakeClient):
            response = await analyze_with_model(JOB, [SimpleNamespace(id=FACT_ID, kind="experience", value="Built Python data pipeline")])
        self.assertEqual(response.input_tokens, 300)
        self.assertEqual(response.output_tokens, 80)
        self.assertFalse(FakeClient.request["store"])
        self.assertTrue(FakeClient.request["text"]["format"]["strict"])
        self.assertEqual(FakeClient.request["model"], "test-model")
        self.assertEqual(FakeClient.headers["Authorization"], "Bearer server-secret")

    async def test_model_refusal_does_not_create_a_proposal(self):
        class RefusingClient:
            def __init__(self, *_args, **_kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

            async def post(self, *_args, **_kwargs):
                return SimpleNamespace(status_code=200, json=lambda: {"status": "completed", "output": [{"type": "message", "content": [{"type": "refusal", "refusal": "Cannot comply"}]}]})

        with patch("apps.api.app.services.tailoring.settings", SimpleNamespace(openai_api_key="server-secret", openai_model="test-model")), \
             patch("apps.api.app.services.tailoring.httpx.AsyncClient", RefusingClient):
            with self.assertRaises(TailoringError):
                await analyze_with_model(JOB, [SimpleNamespace(id=FACT_ID, kind="experience", value="Built Python data pipeline")])
