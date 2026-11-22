# Phase 4: grounded resume tailoring

## Workflow

1. The user uploads a PDF or DOCX, approves extracted career facts, and saves a profile.
2. In the **Tailor** tab, the user selects an original resume and pastes a job posting. **Copy text from current page** fills the text box for review; it does not send anything to the model until **Analyze** is clicked.
3. The API downloads the user's private original resume with their JWT, extracts its text for the comparison view, and sends only the job description and approved career facts to the OpenAI Responses API. The model request uses strict structured JSON output and `store: false`.
4. The server checks that each job requirement and any title or company appears in the posting, every suggested fact ID belongs to approved facts, and each rewrite preserves the same substantive words and counts as that approved fact. Simple connectors and punctuation may change. Unsupported output is rejected. The original text is displayed separately; it is not used as evidence for new claims.
5. The user sees extracted requirements with supporting approved facts, an internal word-overlap relevance estimate, the original resume text, and each before/after rewrite. Rewrites start unselected. The exported PDF includes approved facts and profile contact details; only selected rewrites replace their source fact text.

Drafts are owner-scoped, expire after 24 hours, and are signed with a server-only HMAC key. Export verifies the signature, selected IDs, and unchanged approved facts. The database policy grants no update permission on tailoring drafts. Model token counts are recorded with each draft. Ten successful analyses per account per day are allowed.

## Relevance estimate and limits

The displayed percentage counts job requirement words present across approved facts, with required quotes weighted twice. It can miss synonyms and does not verify that a person truly meets every qualification. It is **not** an employer ATS score or a prediction of an interview. An unevidenced requirement means the approved facts did not provide exact word evidence; it does not prove the applicant lacks that qualification.

The PDF has a single column, standard headings, selectable text, and no graphics or tables. Project and skill entries are ordered by model relevance; experience and education retain approved-fact order because the current profile lacks structured employment dates. The source resume may contain unapproved material, but that material is never copied into the exported PDF. The strict rewrite guard rejects useful synonyms as well as unsupported claims; users can correct the underlying approved fact and analyze again.

## Setup

Set `OPENAI_API_KEY`, optional `OPENAI_MODEL`, and `TAILOR_SIGNING_KEY` in `apps/api/.env`. Generate the signing key with `python -c 'import secrets; print(secrets.token_urlsafe(48))'`. Install the updated API dependencies and run `alembic -c apps/api/alembic.ini upgrade head` in the virtual environment. Rebuild and reload the extension, then start the API as described in the README. No model key or signing key belongs in the extension build.

## Verification

`npm run check` passed with 21 extension tests, 16 API tests, TypeScript, lint and a production build. API tests cover grounded requirements and rewrites, signed-draft tampering, owner isolation, stale approved facts, selected versus unchanged PDF text, and structured model request settings. A sample PDF was rendered and inspected for visual layout and text extraction. The Phase 4 migration also rendered successfully as offline PostgreSQL SQL.

Live Supabase, OpenAI, and Chrome end-to-end tests remain pending because no Supabase project or model credentials were supplied. The automated model tests use a mocked response; they do not establish live model reliability or cost. A staging run with a real account, approved facts, and non-sensitive test posting is needed before using this workflow with real resumes.
