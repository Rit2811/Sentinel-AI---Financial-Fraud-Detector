#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "${BASH_SOURCE[0]%/*}/.." && pwd)
rm -rf \
  "$ROOT/backend/node_modules" \
  "$ROOT/backend/.jest-cache" \
  "$ROOT/backend/coverage" \
  "$ROOT/frontend/node_modules" \
  "$ROOT/frontend/dist" \
  "$ROOT/frontend/coverage"
