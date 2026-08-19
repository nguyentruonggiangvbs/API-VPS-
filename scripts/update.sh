#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$PROJECT_DIR/scripts/deploy-vps.sh" \
  "$PROJECT_DIR" \
  "${1:-main}" \
  "${2:-http://127.0.0.1:9000/api/health}"
