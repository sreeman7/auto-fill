# Phase 7: security and quality

## Changes

- API middleware adds bounded, per-minute limits for each credential and client IP. It returns 429 with `Retry-After`. This limit is process-local; a multi-worker deployment also needs an ingress or managed edge limit.
- API responses include a random `X-Request-ID`, `Cache-Control: no-store`, `X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer`.
- Request monitoring emits one JSON line with the route template, method, status and duration. It omits raw paths, query strings, bodies, IP addresses, authorization tokens and user IDs. Start Uvicorn with `--no-access-log`, and disable any hosting access log that records raw URLs.
- `/api/v1/health` is a liveness check. `/api/v1/ready` returns 200 only when the configured database answers `SELECT 1`; otherwise it returns 503. The PostgreSQL connection has a three-second timeout.
- Hosted `APP_ENV=staging` or `production` requires HTTPS Supabase, server-only keys, a database URL with TLS enabled and explicit extension CORS origins.
- [GitHub Actions verification](../.github/workflows/verify.yml) runs typecheck, lint, tests, build and dependency audits on pull requests and pushes. A passing main-branch run uploads the tested extension bundle as a short-lived artifact. It does not deploy or publish the extension.
- Updated Zod, Vite, Vitest and esbuild after a live npm audit reported seven advisories. The live recheck reported zero. The Python audit found only an outdated local `pip`; upgrading it to 26.3 cleared the scan. The CI job upgrades `pip` before its audit.

## Staging setup

Create a separate Supabase project and API host for staging. Copy `apps/api/.env.staging.example` to `apps/api/.env` and replace every placeholder with staging values. Copy `apps/extension/.env.staging.example` to `apps/extension/.env.staging` and use only the staging Supabase URL, publishable key and HTTPS API URL. Keep the Supabase secret key and database password in the API environment only. Run:

```bash
source .venv/bin/activate
alembic -c apps/api/alembic.ini upgrade head
uvicorn apps.api.app.main:app --host 127.0.0.1 --port 8001 --no-access-log
npm run build:staging
```

The extension ID from the staging build must be added to the API's `ALLOWED_ORIGINS` and the Supabase Auth redirect allowlist. Use a staging API hostname that resolves to the API host; the sample does not create hosting or a database automatically.

## Review and tests

Security tests cover the rate-limit response, bounded limiter memory, secure staging settings, response headers, redacted request logs and readiness states. Other tests cover account isolation, invalid uploads and the no-submit autofill path. The full local check is `npm run check`.

Browser review on the installed versions of Google Chrome and Brave used the checked-in application fixture. Chrome rendered the fixture with its manual submit state untouched. Brave loaded the extension in a temporary headless profile. Google [removed command-line unpacked extension loading from branded Chrome](https://developer.chrome.com/blog/extension-news-june-2025), so the same automated extension-loading method cannot validate Google Chrome. A signed-in Supabase flow and real staging deployment remain pending.

Both dependency audits were run against live advisory services in this workspace after updates and returned no known vulnerabilities. The GitHub Actions workflow has been syntax checked locally but cannot run here without a GitHub Actions runner. No production deployment or Chrome Web Store release is part of this phase.
