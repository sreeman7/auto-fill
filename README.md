# auto-fill

auto-fill is a user-controlled Chrome extension for reviewing and filling job applications. Phase 1 provides local profile storage and deterministic form filling. Phase 2 adds Supabase accounts, account-scoped profiles, private resume uploads, deterministic extraction proposals, and explicit fact approval. Phase 3 adds generic, Greenhouse and Lever form adapters, dynamic form rescanning, and validation reporting. Phase 4 adds grounded job analysis, reviewable resume suggestions, and text-based PDF export. Phase 5 adds screening question drafts and saved, user-approved answers. Phase 6 adds a private application tracker with status updates, duplicate checks, and search. The extension never submits applications.

## Requirements and checks

Requirements: Node.js 20+, npm, Python 3.12+, and Chrome 116+.

```bash
npm install
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e './apps/api[dev]'
npm run check
```

`npm run check` runs TypeScript validation, lint, extension tests, API tests, and the extension build. The API tests use an isolated SQLite database and mocked Supabase responses; they do not contact a live Supabase project.

## Local autofill (no account needed)

```bash
python3 -m http.server 8000 --bind 127.0.0.1
```

Open `http://127.0.0.1:8000/tests/fixtures/application.html` in Chrome. At `chrome://extensions`, enable Developer mode, choose **Load unpacked**, and select this repository's `apps/extension/dist` directory. Click the **auto-fill** toolbar icon while the fixture tab is active. Save a local profile, scan, review the proposed values, and fill. Inspect the page before using its manual test submit button. Reload the extension in `chrome://extensions` after each build. The `greenhouse.html`, `lever.html`, and `dynamic.html` files in the same fixtures directory exercise Phase 3 behavior locally.

## Phase 2 cloud setup

1. Create a Supabase project. Enable email confirmation. Enable Google as a provider if you want Google sign-in.
2. Copy `apps/api/.env.example` to `apps/api/.env` and `apps/extension/.env.example` to `apps/extension/.env`. Set the Supabase URL and publishable key in both files. Set the database URL and **server-only** secret key in the API file. Set `VITE_API_BASE_URL=http://127.0.0.1:8001` in the extension file. Never put the secret key or database password in the extension file.
3. From the repository root, run `alembic -c apps/api/alembic.ini upgrade head` with the virtual environment active. This creates user-scoped tables, row-level security policies, and a private `resumes` bucket.
4. Build and load the extension. Copy its ID from `chrome://extensions` into API `ALLOWED_ORIGINS=chrome-extension://YOUR_EXTENSION_ID`, then run `uvicorn apps.api.app.main:app --host 127.0.0.1 --port 8001` from the repository root. Reload the extension after rebuilding it with the cloud settings.
5. For Google sign-in, add `https://YOUR_EXTENSION_ID.chromiumapp.org/auth` to Supabase Auth's redirect allowlist and complete Google provider setup in Supabase. The extension uses Chrome's identity flow.
6. For password recovery by code, change the Supabase **Reset password** email template to include `{{ .Token }}`, set `VITE_RECOVERY_CODE_ENABLED=true`, and rebuild. The recovery button is hidden until this is configured.

The account tab supports email/password sign-up and sign-in, Google sign-in when configured, sign-out, recovery code flow when configured, and permanent account deletion when the API secret key is configured. A signed-in profile is cached under that account's ID and never automatically replaced with the signed-out profile. Saving a profile while signed in writes both the account copy and its local cache. **Load profile from account** is an explicit action.

Upload a text-based PDF or DOCX (5 MB maximum) from the **Resumes** tab. Each extracted fact remains a suggestion until selected and approved. Approved facts can later be viewed, corrected or removed under **Profile**. Existing verified profile values are preserved; approved contact details fill only empty account fields. Image-only PDFs need OCR, which is not part of Phase 2.

## Phase 4 job analysis and PDF export

After the Phase 2 cloud setup, add a server-only `OPENAI_API_KEY` and a random `TAILOR_SIGNING_KEY` of at least 32 characters to `apps/api/.env`. `OPENAI_MODEL` defaults to `gpt-4o-mini` and can be changed on the server. Keep both secrets out of `apps/extension/.env`. Install the updated API dependencies, then apply the new migration:

```bash
source .venv/bin/activate
python -m pip install -e './apps/api[dev]'
alembic -c apps/api/alembic.ini upgrade head
```

Run the API and reload the built extension. In **Tailor**, choose an uploaded resume, paste a job description or copy text from the current page, then inspect the extracted requirements and before/after proposals. Select each rewrite you approve and export the PDF. The export uses approved career facts even when no rewrite is selected. The [Phase 4 guide](docs/phase-4.md) describes evidence checks and limits.

## Phase 5 screening answers

Use the same server-only `OPENAI_API_KEY` and `TAILOR_SIGNING_KEY` configured for Phase 4. Apply the new migration with `alembic -c apps/api/alembic.ini upgrade head`, restart the API, rebuild the extension and reload it in Chrome. In **Answers**, paste a screening question or select its text on the application page and click **Use selected page text**. Review the question, optionally add job context, choose a draft length and request a draft. Edit the answer, check the explicit approval box and save it. Saved answers can be copied or removed. Sensitive questions are not drafted or saved; answer them directly on the application page. See [Phase 5](docs/phase-5.md) for safety rules and test limits.

## Phase 6 application tracker

Apply the latest migration with `alembic -c apps/api/alembic.ini upgrade head`, restart the API, rebuild the extension and reload it in Chrome. Sign in and open **Tracker** to save a job, record its status, resume version, notes, interview dates and follow-up dates. New records start as **Saved**. After submitting on the job site yourself, edit the record, choose **Applied** or a later status, and explicitly confirm submission. Autofill never changes a tracked status. Duplicate job URLs are blocked; a matching company and title asks for review before you save another role. See [Phase 6](docs/phase-6.md) for API behavior and test limits.

## Repository

- `apps/extension`: MV3 extension, React side panel, local and cloud profile flows.
- `apps/api`: FastAPI routes, SQLAlchemy models, Alembic migration, resume parsing and Supabase Auth/Storage integration.
- `tests/fixtures`: sample application forms.
- `docs/phase-1.md` through `docs/phase-6.md`: scope, review findings, verification and limits.

The API uses the caller's Supabase token for Auth verification and private Storage operations. Database sessions temporarily assume the `authenticated` role with that verified user's ID, so RLS policies apply. The server secret key is used only for account deletion and must never be bundled with the extension.
