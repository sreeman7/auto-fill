# auto-fill

auto-fill is a user-controlled job application helper. Phase 1 is a local Chrome Manifest V3 extension with a React side panel, a saved test profile, form scanning, deterministic matching, read-back verification, and a sample application form. It does not submit applications.

## Run Phase 1

Requirements: Node.js 20+, npm, Python 3.12+, and Chrome 116+.

```bash
npm install
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e './apps/api[dev]'
npm run check
python3 -m http.server 8000 --bind 127.0.0.1
```

Open `http://127.0.0.1:8000/tests/fixtures/application.html` in Chrome. At `chrome://extensions`, enable Developer mode, choose **Load unpacked**, and select the absolute `apps/extension/dist` folder in this repository. Click the **auto-fill** toolbar icon while the fixture tab is active. In the side panel, save a profile, scan the page, review the proposed values, and click **Fill reviewed fields**. Inspect the form before using its manual test submit button. After source changes, run `npm run build` and reload the extension in `chrome://extensions`.

The local fixture never sends an application to a server. Extension access is temporary and begins when you click its toolbar icon on a page. Chrome restricts extension injection into some pages, including `chrome://` URLs.

## Repository

- `apps/extension`: Chrome extension, React side panel, local storage, field detector, matcher and filler.
- `apps/api`: FastAPI project scaffold with a health endpoint. The extension does not call it yet.
- `tests/fixtures`: local forms for manual and automated verification.
- `docs`: architecture notes and phase status.

The authenticated API, database, resume import, AI features, ATS adapters, and application tracker are later phases. Phase 1 needs no environment variables, external accounts, or API secrets. To run the optional health endpoint: `python3 -m uvicorn apps.api.app.main:app --reload` and open `http://127.0.0.1:8000/api/v1/health` (use a different port if the fixture server is running).

## Checks

`npm run check` runs TypeScript validation, lint, extension and API unit tests, and a production build. Chrome manual smoke testing uses the steps above. See `docs/phase-1.md` for current coverage and limits.
