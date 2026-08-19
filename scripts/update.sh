#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

git fetch origin main
git merge --ff-only origin/main
docker compose up -d --build --remove-orphans

for attempt in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:9000/api/health >/dev/null; then
    echo "API‑VPS đã cập nhật thành công."
    docker compose ps
    exit 0
  fi
  sleep 2
done

echo "LỖI: Health check API‑VPS thất bại." >&2
docker compose logs --tail=150 api-vps >&2
exit 1
