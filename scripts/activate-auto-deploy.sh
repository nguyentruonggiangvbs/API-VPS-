#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

REPOSITORY="${REPOSITORY:-nguyentruonggiangvbs/API-VPS-}"
VPS_HOST="${VPS_HOST:-187.127.124.155}"
VPS_PORT="${VPS_PORT:-22}"
DEPLOY_USER="${DEPLOY_USER:-api-vps-deploy}"
PROJECT_DIR="${PROJECT_DIR:-/opt/api-vps}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:9000/api/health}"
PUBLIC_URL="${PUBLIC_URL:-}"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

[[ "$(id -u)" -eq 0 ]] || fail "Run this script as root"
[[ "$REPOSITORY" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || fail "REPOSITORY is invalid"
[[ "$VPS_HOST" =~ ^[A-Za-z0-9._-]+$ ]] || fail "VPS_HOST is invalid"
[[ "$VPS_PORT" =~ ^[0-9]+$ ]] || fail "VPS_PORT must be numeric"
(( VPS_PORT >= 1 && VPS_PORT <= 65535 )) || fail "VPS_PORT out of range"
[[ "$DEPLOY_USER" =~ ^[a-z_][a-z0-9_-]*$ ]] || fail "DEPLOY_USER is invalid"
[[ "$PROJECT_DIR" =~ ^/[A-Za-z0-9._/-]+$ ]] || fail "PROJECT_DIR is invalid"
[[ "$HEALTH_URL" =~ ^https?://[^[:space:]\'\"]+$ ]] || fail "HEALTH_URL is invalid"

for command_name in gh git docker ssh-keygen install awk getent useradd usermod runuser; do
  command -v "$command_name" >/dev/null 2>&1 || fail "Missing command: $command_name"
done

docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is required"
gh auth status --hostname github.com >/dev/null 2>&1 || {
  fail "GitHub CLI is not logged in. Run: gh auth login -h github.com -p https -w -s repo"
}

[[ -d "$PROJECT_DIR/.git" ]] || fail "Project repository not found: $PROJECT_DIR"
[[ -f /etc/ssh/ssh_host_ed25519_key.pub ]] || fail "OpenSSH Ed25519 host key is missing"

if ! id "$DEPLOY_USER" >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash "$DEPLOY_USER"
fi

getent group docker >/dev/null 2>&1 || fail "Docker group does not exist"
usermod -aG docker "$DEPLOY_USER"

deploy_home="$(getent passwd "$DEPLOY_USER" | cut -d: -f6)"
[[ -n "$deploy_home" && -d "$deploy_home" ]] || fail "Deploy user home is invalid"

install -d -m 700 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "$deploy_home/.ssh"

key_dir="/root/.ssh/api-vps-github-actions"
private_key="$key_dir/id_ed25519"
public_key="$private_key.pub"
install -d -m 700 "$key_dir"

if [[ ! -f "$private_key" || ! -f "$public_key" ]]; then
  rm -f "$private_key" "$public_key"
  ssh-keygen \
    -t ed25519 \
    -N '' \
    -C 'api-vps-github-actions' \
    -f "$private_key" >/dev/null
fi

chmod 600 "$private_key"
chmod 644 "$public_key"

authorized_keys="$deploy_home/.ssh/authorized_keys"
touch "$authorized_keys"
chmod 600 "$authorized_keys"
chown "$DEPLOY_USER:$DEPLOY_USER" "$authorized_keys"

public_line="$(cat "$public_key")"
if ! grep -Fqx "$public_line" "$authorized_keys"; then
  printf '%s\n' "$public_line" >> "$authorized_keys"
fi
chown -R "$DEPLOY_USER:$DEPLOY_USER" "$deploy_home/.ssh"

chown -R "$DEPLOY_USER:$DEPLOY_USER" "$PROJECT_DIR"
runuser -u "$DEPLOY_USER" -- \
  git config --global --add safe.directory "$PROJECT_DIR"

read -r host_key_type host_key_data _ < /etc/ssh/ssh_host_ed25519_key.pub
host_token="$VPS_HOST"
if [[ "$VPS_PORT" != "22" ]]; then
  host_token="[$VPS_HOST]:$VPS_PORT"
fi

known_hosts_file="$(mktemp)"
trap 'rm -f "$known_hosts_file"' EXIT
printf '%s %s %s\n' \
  "$host_token" \
  "$host_key_type" \
  "$host_key_data" > "$known_hosts_file"
chmod 600 "$known_hosts_file"

printf '%s' "$VPS_HOST" | gh secret set VPS_HOST --repo "$REPOSITORY"
printf '%s' "$VPS_PORT" | gh secret set VPS_PORT --repo "$REPOSITORY"
printf '%s' "$DEPLOY_USER" | gh secret set VPS_USER --repo "$REPOSITORY"
gh secret set VPS_SSH_KEY --repo "$REPOSITORY" < "$private_key"
gh secret set VPS_KNOWN_HOSTS --repo "$REPOSITORY" < "$known_hosts_file"
printf '%s' "$PROJECT_DIR" | gh secret set VPS_PROJECT_PATH --repo "$REPOSITORY"
printf '%s' "$HEALTH_URL" | gh secret set VPS_HEALTH_URL --repo "$REPOSITORY"

if [[ -n "$PUBLIC_URL" ]]; then
  printf '%s' "$PUBLIC_URL" | gh secret set VPS_PUBLIC_URL --repo "$REPOSITORY"
fi

gh workflow run deploy-vps.yml \
  --repo "$REPOSITORY" \
  --ref main

cat <<EOF

SUCCESS: GitHub → VPS auto deploy has been activated.

Repository:  $REPOSITORY
Deploy user: $DEPLOY_USER
Project:     $PROJECT_DIR
Health URL:  $HEALTH_URL

The workflow was triggered. Check:
  gh run list --repo "$REPOSITORY" --workflow deploy-vps.yml --limit 3
EOF
