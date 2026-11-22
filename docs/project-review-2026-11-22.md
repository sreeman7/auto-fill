# auto-fill project review — 22 November 2026

## Current product

auto-fill provides local profile editing, deterministic review and form filling, optional Supabase accounts, private resume upload with rule-based fact proposals, and an application tracker. The extension requires the user to inspect values and submit each application. Model-backed Tailor and Answers features were removed from the extension and API.

## Removal review

- The extension no longer requests job descriptions or selected question text, shows model-backed tabs, or bundles model service credentials.
- The API no longer exposes tailoring or screening routes. It retains profile, resume, fact, application, account-deletion, health and readiness routes.
- Migration `0005_remove_ai` removes the three unused draft and answer tables only after verifying they are empty. The live Supabase project had zero rows in all three tables. The remaining four application tables retain row-level security.
- The local API environment and checked-in examples no longer contain model credentials or signing keys. Historical migrations remain so existing databases can upgrade safely to the removal revision.
- The privacy policy, store listing and screenshots now describe and show the current feature set.

## Verification

- `npm run check` with the project virtual environment on `PATH` passed: TypeScript, lint, 22 extension tests, 21 API tests, build and release-asset checks.
- The disposable Brave browser smoke test passed for Greenhouse, Lever, generic and dynamic fixtures, with no automatic submission or file upload. It also checked the five remaining tabs and first-run privacy wording.
- Live Supabase migration is at `0005_remove_ai`. The retained `profiles`, `resumes`, `career_facts` and `applications` tables have row-level security enabled.

## Remaining beta work

The signed-in extension flow, real employer sites, Chrome Web Store installation, Google sign-in and production hosting need separate validation. The public privacy URL and monitored contact are required before beta packaging.
