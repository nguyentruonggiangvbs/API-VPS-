#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

command -v docker >/dev/null 2>&1 || {
  echo "LỖI: Docker chưa được cài." >&2
  exit 1
}
docker compose version >/dev/null 2>&1 || {
  echo "LỖI: Docker Compose v2 chưa được cài." >&2
  exit 1
}

mkdir -p data/backups data/jobs data/logs config

if [ ! -f .env ]; then
  if command -v openssl >/dev/null 2>&1; then
    API_KEY_VALUE="$(openssl rand -hex 32)"
  else
    API_KEY_VALUE="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
  fi
  cat > .env <<EOF
API_KEY=$API_KEY_VALUE
BIND_ADDRESS=127.0.0.1
PORT=9000
MANAGED_ROOTS=opt=/opt;www=/var/www
GIT_HTTP_USERNAME=x-access-token
GIT_HTTP_TOKEN=
MAX_READ_BYTES=2097152
MAX_WRITE_BYTES=4194304
MAX_UPLOAD_BYTES=104857600
METRICS_INTERVAL_SECONDS=5
METRICS_HISTORY_POINTS=720
EOF
  chmod 600 .env
  echo "Đã tạo .env và API key mới."
fi

if [ ! -f config/projects.json ]; then
  cp config/projects.example.json config/projects.json
  echo "Đã tạo config/projects.json từ mẫu."
fi

docker compose up -d --build
docker compose ps

API_KEY_VALUE="$(sed -n 's/^API_KEY=//p' .env | head -n 1)"
echo
echo "API‑VPS đã chạy tại http://127.0.0.1:9000"
echo "API key đăng nhập (lưu lại ở nơi an toàn):"
echo "$API_KEY_VALUE"
echo
echo "Để truy cập từ xa, cấu hình Nginx + HTTPS:"
echo "  sudo ./scripts/install-nginx.sh ten-mien-cua-ban"
