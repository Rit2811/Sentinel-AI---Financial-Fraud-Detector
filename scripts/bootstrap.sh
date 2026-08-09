#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "${BASH_SOURCE[0]%/*}/.." && pwd)
(cd "$ROOT/backend" && uv sync --frozen)
(cd "$ROOT/frontend" && npm ci)
