#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
COMPOSE=(docker compose -f "$ROOT/infrastructure/compose.yaml")

cleanup() {
  "${COMPOSE[@]}" down >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "[backend] format, lint, unit tests"
(
  cd "$ROOT/backend"
  npm run format:check
  npm run lint
  npm test
)

echo "[frontend] format, lint, tests, build"
(
  cd "$ROOT/frontend"
  npm run format:check
  npm run lint
  npm run test
  npm run build
)

echo "[ml] lock, format, lint, unit tests (dataset download excluded)"
(
  cd "$ROOT/services/ml"
  UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.uv-python uv sync --locked
  UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.uv-python uv run ruff format --check .
  UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.uv-python uv run ruff check .
  UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.uv-python uv run pytest -q
)

echo "[compose] validate, build, start, wait"
"${COMPOSE[@]}" config --quiet
"${COMPOSE[@]}" build
"${COMPOSE[@]}" up -d --wait
"${COMPOSE[@]}" ps

echo "[database] Task 3 migration cycle and integration tests"
TASK3_DATABASE_URL="postgresql://${POSTGRES_USER:-sentinel}:${POSTGRES_PASSWORD:-sentinel_local_only}@127.0.0.1:${POSTGRES_PORT:-15432}/${POSTGRES_DB:-sentinel}"
(
  cd "$ROOT/backend"
  DATABASE_URL="$TASK3_DATABASE_URL" npm run migrate:up
  DATABASE_URL="$TASK3_DATABASE_URL" npm run migrate:down
  DATABASE_URL="$TASK3_DATABASE_URL" npm run migrate:up
  TEST_DATABASE_URL="$TASK3_DATABASE_URL" npm run test:integration
)

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

echo "Task 2/3 regression and Task 4 code verification passed"
