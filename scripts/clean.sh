#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "${BASH_SOURCE[0]%/*}/.." && pwd)
rm -rf \
  "$ROOT/backend/.venv" \
  "$ROOT/backend/.pytest_cache" \
  "$ROOT/backend/.mypy_cache" \
  "$ROOT/backend/.ruff_cache" \
  "$ROOT/frontend/node_modules" \
  "$ROOT/frontend/dist" \
  "$ROOT/frontend/coverage"
