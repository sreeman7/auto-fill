#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

if [[ ! -x .venv/bin/python ]]; then
  echo "Missing .venv. Follow the installation steps in README.md first." >&2
  exit 1
fi
if [[ ! -f apps/api/.env || ! -f apps/extension/.env ]]; then
  echo "Missing local .env files. Follow the cloud setup in README.md first." >&2
  exit 1
fi
if [[ ! -f apps/extension/dist/manifest.json ]]; then
  echo "Missing extension build. Run npm run build first." >&2
  exit 1
fi

api_pid=""
fixtures_pid=""
cleanup() {
  if [[ -n "$api_pid" ]]; then kill "$api_pid" 2>/dev/null || true; fi
  if [[ -n "$fixtures_pid" ]]; then kill "$fixtures_pid" 2>/dev/null || true; fi
  wait 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

.venv/bin/python -m uvicorn apps.api.app.main:app --host 127.0.0.1 --port 8001 --no-access-log &
api_pid=$!
.venv/bin/python -m http.server 8000 --bind 127.0.0.1 >/dev/null 2>&1 &
fixtures_pid=$!

echo "auto-fill API: http://127.0.0.1:8001/api/v1/health"
echo "Test form:     http://127.0.0.1:8000/tests/fixtures/application.html"
echo "Extension:     $project_root/apps/extension/dist"
echo "Press Ctrl+C to stop both local servers."

while kill -0 "$api_pid" 2>/dev/null && kill -0 "$fixtures_pid" 2>/dev/null; do
  sleep 1
done
echo "A local server stopped. Check the output above and whether ports 8000 and 8001 are in use." >&2
exit 1
