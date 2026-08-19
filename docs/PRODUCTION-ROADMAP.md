# Production Status

## v1.0.0 — hoàn thành

- [x] FastAPI modular backend
- [x] Dashboard responsive
- [x] Monitoring realtime/history/processes
- [x] File Manager allowlist
- [x] Docker Manager
- [x] Deploy Manager + rollback
- [x] Backup + restore
- [x] Audit log
- [x] API key, rate limit, CSP, security headers
- [x] Docker read-only filesystem + no-new-privileges
- [x] Nginx template
- [x] CI compile/JavaScript/shell/security/Compose/container smoke test
- [x] SSH auto deploy + lock + backup + health check + rollback
- [x] Project memory và deployment documentation

## Kích hoạt vận hành

Còn đúng một thao tác hạ tầng ngoài repository:

1. cấu hình GitHub Actions secrets;
2. chạy `scripts/install.sh` lần đầu hoặc deploy thủ công;
3. cấu hình Nginx + HTTPS;
4. bỏ truy cập công khai trực tiếp tới port `9000`.

## Sau v1.0.0 — tùy chọn

- Multi-user/RBAC.
- 2FA hoặc SSO.
- Persistent metrics database.
- Remote backup storage.
- Alerting Telegram/email.
- Docker image update policy.
- Multi-VPS inventory.

Các mục tùy chọn không ngăn v1.0.0 vận hành.
