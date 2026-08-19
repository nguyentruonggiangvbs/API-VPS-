# API-VPS Context

## Mục tiêu

API-VPS là bảng điều khiển web quản trị VPS của ĐI ƠI. GitHub là source of truth để ChatGPT/Codex có thể đọc lại kiến trúc, tiếp tục phát triển và triển khai có kiểm soát.

## Kiến trúc chính thức

```text
ChatGPT / Codex
        ↓
GitHub repository `API-VPS-`
        ↓ CI + SSH auto deploy
VPS Hostinger
        ├── api-vps (localhost:9000)
        └── camera-pc (port 3000, phải bảo toàn)
        ↓
Nginx + HTTPS
        ↓
Dashboard quản trị
```

## VPS

- Hệ điều hành: Ubuntu 24.04 LTS
- Source: `/opt/api-vps`
- API nội bộ: `http://127.0.0.1:9000`
- Health: `http://127.0.0.1:9000/api/health`
- Truy cập từ Internet chỉ qua Nginx + HTTPS

Không lưu mật khẩu, token, API key, SSH private key hoặc `.env` trong repository.

## Chức năng hoàn thành

- Dashboard tổng quan và monitoring realtime/history/processes.
- File Manager allowlist đầy đủ.
- Docker Manager đầy đủ.
- Deploy Manager theo project allowlist, health check và rollback.
- Backup/restore.
- Audit log.
- API key, rate limit, CSP và security headers.
- CI compile/JavaScript/shell/security/Compose/container smoke test.
- SSH auto deploy có lock, backup, health check và rollback.

## Quy trình phát triển

1. Tạo branch từ `main`.
2. Sửa source trên GitHub/Codex.
3. Mở pull request.
4. Chờ CI xanh.
5. Merge vào `main`.
6. GitHub Actions deploy qua SSH nếu repository secrets đã cấu hình.

## Quyết định an toàn

- Không có web terminal tùy ý.
- Không có route `/control` không xác thực.
- Không public port `9000` hoặc deploy-agent port.
- File Manager chỉ truy cập `MANAGED_ROOTS`.
- Docker socket tương đương quyền root; chỉ cấp API key cho quản trị viên.
- Không chỉnh sửa hoặc restart `camera-pc` trong quy trình API-VPS.

## Đọc tiếp

- `README.md`
- `docs/PROJECT-MEMORY.md`
- `docs/DEPLOYMENT.md`
- `docs/AUTO-DEPLOY-ARCHITECTURE.md`
- `docs/VPS-SECURITY.md`
