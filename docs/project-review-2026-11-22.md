# auto-fill whole-project review — 22 November 2026

## Scope

Reviewed extension form detection, matching, filling, dynamic rescanning, local profile and account state; API authentication, ownership, resume import, approved facts, tailoring, screening, tracker, deletion, rate limits and logging; migrations, CI, store preparation; and the attached product specification. The current repository is a local beta candidate, not a released or live-cloud-validated product.

## Defects fixed in this review

1. Resume approval could raise `NameError` when selected name and email facts were used to create the first profile. Imported `ProfilePayload` and added an API regression test for that branch.
2. A cloud-enabled side panel could load the signed-out local profile while restoring a saved account session. Profile access now waits for session restoration, and a change of account clears displayed profile and form state before the new account profile loads.
3. Browser smoke coverage now includes a field inserted after the initial scan. The side panel detects the change and requires a renewed review before filling.

## Verification

- `npm run check` with `.venv/bin` first on `PATH`: passed, including 24 extension tests, 36 API tests, typecheck, lint, production build and release artwork validation.
- `python3 tests/browser_beta_smoke.py`: passed in a temporary headless Brave profile against Greenhouse, Lever, generic and dynamic local fixtures. It confirmed synthetic email fill, no form submission and no file upload.
- A synthetic `build:staging` with example service origins passed the same four browser fixtures, including the session-restoration path with no signed-in user. The normal local build was restored afterward. This does not verify a real Supabase account or service.
- `alembic -c apps/api/alembic.ini upgrade head --sql` with a dummy PostgreSQL URL: all four migrations generated SQL. This is a syntax check, not a live Supabase migration or RLS test.
- `npm audit --audit-level=high --json`: the npm advisory service reported zero known vulnerabilities.
- `.venv/bin/pip-audit --desc off`: the Python advisory service reported no known vulnerabilities in installed third-party packages; the local editable `auto-fill-api` package is not in PyPI and was skipped.
- A scan of the built extension found none of the server-only secret variable names or PostgreSQL URLs. `git diff --check` passed.

## Open product and release gaps

| Priority | Finding | Evidence and consequence |
| --- | --- | --- |
| High | No live cloud validation | No Supabase project or hosted API is configured. Email and Google sign-in, Auth redirects, storage RLS, account deletion, live migrations and model requests have only mocked/local coverage. Do not invite real users yet. |
| High | Store release is blocked | The privacy contact and public policy URL are placeholders, and the beta package gate refuses to produce a ZIP. The Chrome Web Store install, privacy declarations and trusted-tester flow remain untested. |
| Medium | Direct experience editing is missing | The local Profile screen edits contact and education fields, while experience facts come from a cloud resume import. The specification's P0 profile editor calls for direct experience editing. |
| Medium | Tailored versions and preview are missing | The API exports a PDF from approved facts, but does not save a distinct tailored resume version or show the rendered PDF before export. The specification calls for versioning and preview. |
| Medium | Separate consent and deletion controls need design | The first-run notice records one broad acknowledgement. The specification calls for separate cloud, resume-analysis and diagnostics choices, plus data export and defined retention rules. |
| Medium | Release targets are not measured | Fixture tests show safe behavior, but there is no measured 95% field accuracy/required-field recall, median fill latency, accessibility audit or live Greenhouse/Lever compatibility matrix. |

The local fixes above do not resolve those broader gaps. A private beta needs the cloud service, policy contact, public policy URL, Chrome install and real-site testing before release review.
