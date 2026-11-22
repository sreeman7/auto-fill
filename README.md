# auto-fill

auto-fill is a user-controlled Chrome extension for reviewing and filling job applications. Phase 1 provides local profile storage and deterministic form filling. Phase 2 adds Supabase accounts, account-scoped profiles, private resume uploads, deterministic extraction proposals, and explicit fact approval. The extension never submits applications.

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

Open `http://127.0.0.1:8000/tests/fixtures/application.html` in Chrome. At `chrome://extensions`, enable Developer mode, choose **Load unpacked**, and select this repository's `apps/extension/dist` directory. Click the **auto-fill** toolbar icon while the fixture tab is active. Save a local profile, scan, review the proposed values, and fill. Inspect the page before using its manual test submit button. Reload the extension in `chrome://extensions` after each build.

## Phase 2 cloud setup

1. Create a Supabase project. Enable email confirmation. Enable Google as a provider if you want Google sign-in.
2. Copy `apps/api/.env.example` to `apps/api/.env` and `apps/extension/.env.example` to `apps/extension/.env`. Set the Supabase URL and publishable key in both files. Set the database URL and **server-only** secret key in the API file. Set `VITE_API_BASE_URL=http://127.0.0.1:8001` in the extension file. Never put the secret key or database password in the extension file.
3. From the repository root, run `alembic -c apps/api/alembic.ini upgrade head` with the virtual environment active. This creates user-scoped tables, row-level security policies, and a private `resumes` bucket.
4. Build and load the extension. Copy its ID from `chrome://extensions` into API `ALLOWED_ORIGINS=chrome-extension://YOUR_EXTENSION_ID`, then run `uvicorn apps.api.app.main:app --host 127.0.0.1 --port 8001` from the repository root. Reload the extension after rebuilding it with the cloud settings.
5. For Google sign-in, add `https://YOUR_EXTENSION_ID.chromiumapp.org/auth` to Supabase Auth's redirect allowlist and complete Google provider setup in Supabase. The extension uses Chrome's identity flow.
6. For password recovery by code, change the Supabase **Reset password** email template to include `{{ .Token }}`, set `VITE_RECOVERY_CODE_ENABLED=true`, and rebuild. The recovery button is hidden until this is configured.

The account tab supports email/password sign-up and sign-in, Google sign-in when configured, sign-out, recovery code flow when configured, and permanent account deletion when the API secret key is configured. A signed-in profile is cached under that account's ID and never automatically replaced with the signed-out profile. Saving a profile while signed in writes both the account copy and its local cache. **Load profile from account** is an explicit action.

Upload a text-based PDF or DOCX (5 MB maximum) from the **Resumes** tab. Each extracted fact remains a suggestion until selected and approved. Approved facts can later be viewed, corrected or removed under **Profile**. Existing verified profile values are preserved; approved contact details fill only empty account fields. Image-only PDFs need OCR, which is not part of Phase 2.

## Repository

- `apps/extension`: MV3 extension, React side panel, local and cloud profile flows.
- `apps/api`: FastAPI routes, SQLAlchemy models, Alembic migration, resume parsing and Supabase Auth/Storage integration.
- `tests/fixtures`: sample application form.
- `docs/phase-1.md` and `docs/phase-2.md`: scope, review findings, verification and limits.

The API uses the caller's Supabase token for Auth verification and private Storage operations. Database sessions temporarily assume the `authenticated` role with that verified user's ID, so RLS policies apply. The server secret key is used only for account deletion and must never be bundled with the extension.
