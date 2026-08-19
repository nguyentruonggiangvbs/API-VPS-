#!/usr/bin/env sh
set -eu

DOMAIN="${1:-}"
[ -n "$DOMAIN" ] || {
  echo "Cách dùng: sudo ./scripts/install-nginx.sh api.example.com" >&2
  exit 2
}
[ "$(id -u)" -eq 0 ] || {
  echo "Hãy chạy bằng sudo hoặc root." >&2
  exit 1
}
command -v nginx >/dev/null 2>&1 || {
  echo "LỖI: Nginx chưa được cài." >&2
  exit 1
}

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
TARGET="/etc/nginx/sites-available/api-vps.conf"

sed "s/__SERVER_NAME__/$DOMAIN/g" \
  "$ROOT_DIR/nginx/api-vps.conf.example" > "$TARGET"
ln -sfn "$TARGET" /etc/nginx/sites-enabled/api-vps.conf
nginx -t
systemctl reload nginx

echo "Nginx đã proxy http://$DOMAIN tới API‑VPS."
echo "BẮT BUỘC bật HTTPS trước khi nhập API key từ Internet."
echo "Ví dụ: certbot --nginx -d $DOMAIN"
