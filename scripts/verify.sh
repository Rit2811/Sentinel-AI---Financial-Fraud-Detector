#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
COMPOSE=(docker compose -f "$ROOT/infrastructure/compose.yaml")

cleanup() {
  "${COMPOSE[@]}" down >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "[backend] format, lint, types, tests"
(
  cd "$ROOT/backend"
  uv run ruff format --check .
  uv run ruff check .
  uv run mypy src
  uv run pytest
)

echo "[frontend] format, lint, types, tests, build"
(
  cd "$ROOT/frontend"
  npm run format:check
  npm run lint
  npm run typecheck
  npm run test
  npm run build
)

echo "[compose] validate, build, start, wait"
"${COMPOSE[@]}" config --quiet
"${COMPOSE[@]}" build
"${COMPOSE[@]}" up -d --wait
"${COMPOSE[@]}" ps

echo "[smoke] API and web"
curl --fail --silent --show-error http://127.0.0.1:${API_PORT:-18000}/health
curl --fail --silent --show-error http://127.0.0.1:${API_PORT:-18000}/ready
curl --fail --silent --show-error http://127.0.0.1:${WEB_PORT:-15173}/ >/dev/null

echo "[failure semantics] pause Redis; health stays live and readiness fails"
"${COMPOSE[@]}" pause redis
curl --fail --silent --show-error http://127.0.0.1:${API_PORT:-18000}/health >/dev/null
status=$(curl --silent --output /tmp/sentinel-ready.json --write-out '%{http_code}' http://127.0.0.1:${API_PORT:-18000}/ready)
test "$status" = "503"
grep -q '"redis":false' /tmp/sentinel-ready.json

echo "[recovery] unpause Redis and restart without rebuilding"
"${COMPOSE[@]}" unpause redis
"${COMPOSE[@]}" restart
"${COMPOSE[@]}" up -d --wait
curl --fail --silent --show-error http://127.0.0.1:${API_PORT:-18000}/ready >/dev/null

echo "[logs] recent bounded output"
"${COMPOSE[@]}" logs --no-color --tail=100

echo "Task 2 verification passed"
