#!/usr/bin/env bash
set -Eeuo pipefail
umask 027

PROJECT_DIR="${1:-/opt/api-vps}"
BRANCH="${2:-main}"
HEALTH_URL="${3:-http://127.0.0.1:9000/api/health}"
HEALTH_ATTEMPTS="${HEALTH_ATTEMPTS:-45}"
HEALTH_DELAY_SECONDS="${HEALTH_DELAY_SECONDS:-2}"
KEEP_DEPLOY_BACKUPS="${KEEP_DEPLOY_BACKUPS:-10}"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

log() {
  printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

[[ "$PROJECT_DIR" == /* ]] || fail "PROJECT_DIR must be an absolute path"
[[ "$PROJECT_DIR" =~ ^/[A-Za-z0-9._/-]+$ ]] || fail "PROJECT_DIR contains unsupported characters"
[[ "$BRANCH" =~ ^[A-Za-z0-9._/-]+$ ]] || fail "BRANCH is invalid"
[[ "$HEALTH_URL" =~ ^https?://[^[:space:]\'\"]+$ ]] || fail "HEALTH_URL is invalid"
[[ "$HEALTH_ATTEMPTS" =~ ^[0-9]+$ ]] || fail "HEALTH_ATTEMPTS must be numeric"
[[ "$HEALTH_DELAY_SECONDS" =~ ^[0-9]+$ ]] || fail "HEALTH_DELAY_SECONDS must be numeric"
[[ "$KEEP_DEPLOY_BACKUPS" =~ ^[0-9]+$ ]] || fail "KEEP_DEPLOY_BACKUPS must be numeric"

(( HEALTH_ATTEMPTS >= 1 && HEALTH_ATTEMPTS <= 180 )) || fail "HEALTH_ATTEMPTS out of range"
(( HEALTH_DELAY_SECONDS >= 1 && HEALTH_DELAY_SECONDS <= 30 )) || fail "HEALTH_DELAY_SECONDS out of range"
(( KEEP_DEPLOY_BACKUPS >= 1 && KEEP_DEPLOY_BACKUPS <= 50 )) || fail "KEEP_DEPLOY_BACKUPS out of range"

for command_name in git docker curl flock tar python3; do
  command -v "$command_name" >/dev/null 2>&1 || fail "Missing required command: $command_name"
done

[[ -d "$PROJECT_DIR/.git" ]] || fail "Git repository not found: $PROJECT_DIR"

cd "$PROJECT_DIR"

mkdir -p data/deploy/backups data/deploy/logs
exec 9>data/deploy/.deploy.lock
flock -n 9 || fail "Another API-VPS deployment is already running"

timestamp="$(date -u +'%Y%m%dT%H%M%SZ')"
backup_dir="$PROJECT_DIR/data/deploy/backups/$timestamp"
deploy_log="$PROJECT_DIR/data/deploy/logs/$timestamp.log"
mkdir -p "$backup_dir"
touch "$deploy_log"
chmod 600 "$deploy_log"

exec > >(tee -a "$deploy_log") 2>&1

previous_sha="$(git rev-parse HEAD)"
log "Deployment started previous_sha=$previous_sha branch=$BRANCH"

git status --porcelain=v1 > "$backup_dir/git-status.txt"
git diff --binary > "$backup_dir/local-changes.patch"
git diff --cached --binary > "$backup_dir/local-index.patch"

for runtime_file in .env config/projects.json; do
  if [[ -f "$runtime_file" ]]; then
    install -m 600 "$runtime_file" "$backup_dir/$(basename "$runtime_file")"
  fi
done

git fetch --prune origin "$BRANCH"
target_sha="$(git rev-parse "origin/$BRANCH")"
log "Fetched target_sha=$target_sha"

if [[ "$target_sha" == "$previous_sha" ]]; then
  log "Source is already current; rebuilding to verify configuration"
fi

git reset --hard "$target_sha"
git clean -fd \
  -e .env \
  -e data \
  -e config/projects.json

chmod 0755 scripts/*.sh

if [[ ! -f .env ]]; then
  log "No .env found; running one-time installer"
  ./scripts/install.sh
else
  docker compose config -q
  docker compose build --pull
  docker compose up -d --remove-orphans
fi

health_check() {
  local attempt
  for ((attempt = 1; attempt <= HEALTH_ATTEMPTS; attempt++)); do
    if curl --fail --silent --show-error \
      --max-time 10 \
      -H 'Cache-Control: no-cache' \
      "$HEALTH_URL" >/dev/null; then
      return 0
    fi
    sleep "$HEALTH_DELAY_SECONDS"
  done
  return 1
}

if ! health_check; then
  log "Health check failed for target_sha=$target_sha; starting rollback"
  docker compose logs --tail=250 api-vps || true

  git reset --hard "$previous_sha"
  git clean -fd \
    -e .env \
    -e data \
    -e config/projects.json
  chmod 0755 scripts/*.sh
  docker compose up -d --build --remove-orphans

  if health_check; then
    log "Rollback completed active_sha=$previous_sha"
  else
    log "Rollback health check also failed"
    docker compose logs --tail=250 api-vps || true
  fi
  exit 1
fi

python3 - \
  "$PROJECT_DIR/data/deploy/status.json" \
  "$previous_sha" \
  "$target_sha" \
  "$BRANCH" <<'PY'
import json
import pathlib
import sys
from datetime import datetime, timezone

path, previous_sha, target_sha, branch = sys.argv[1:]
payload = {
    "state": "healthy",
    "branch": branch,
    "previous_sha": previous_sha,
    "active_sha": target_sha,
    "updated_at": datetime.now(timezone.utc).isoformat(),
}
target = pathlib.Path(path)
temporary = target.with_suffix(target.suffix + ".tmp")
temporary.write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
temporary.replace(target)
PY

docker compose ps
log "Deployment completed active_sha=$target_sha"

find "$PROJECT_DIR/data/deploy/backups" \
  -mindepth 1 -maxdepth 1 -type d \
  -printf '%T@ %p\n' \
  | sort -nr \
  | awk '{print $2}' \
  | tail -n "+$((KEEP_DEPLOY_BACKUPS + 1))" \
  | while IFS= read -r old_backup; do
      [[ -n "$old_backup" ]] || continue
      rm -rf -- "$old_backup"
    done
