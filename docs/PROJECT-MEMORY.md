# API-VPS Project Memory

## Trạng thái

**API-VPS Control Center v1.0.0 đã hoàn thiện ở mức production-ready trong repository.**

Source chính:

```text
nguyentruonggiangvbs/API-VPS-
branch: main
```

## VPS hiện tại

Thông tin công khai để định tuyến triển khai:

- Ubuntu 24.04 LTS
- project: `/opt/api-vps`
- API nội bộ: `127.0.0.1:9000`
- container khác cần bảo toàn: `camera-pc`, port `3000`
- Nginx/HTTPS phải đứng trước API-VPS khi truy cập từ Internet

Không lưu mật khẩu, API key, PAT, private key hoặc nội dung `.env` trong GitHub.

## Chức năng v1.0.0

- Dashboard SPA responsive.
- CPU, RAM, disk, network, uptime, lịch sử và process monitor.
- File Manager allowlist: list/read/write/create/upload/download/search/rename/delete.
- Docker Manager: list/inspect/stats/log/start/stop/restart/pause/unpause.
- Deploy Manager allowlist với Git fast-forward, Docker Compose/command arrays, health check và rollback.
- Backup Manager: create/list/download/delete/restore.
- Audit log, API key, rate limit, security headers và CSP.
- Nginx template, installer, updater, CI, container smoke test.
- SSH auto deploy có backup, lock, health check và rollback.
- Script kích hoạt một lần tự tạo user/key và GitHub Actions Secrets.

## Quyết định bảo mật

- Không có arbitrary web terminal.
- Không có route `/control` không xác thực.
- Không chạy `shell=True`, `os.system` hoặc `subprocess.getoutput`.
- Không public Docker socket; socket chỉ mount trong container quản trị.
- API bind localhost mặc định.
- File Manager chỉ truy cập `MANAGED_ROOTS`.
- Container `api-vps` được bảo vệ khỏi self-stop qua dashboard.
- `camera-pc` không bị sửa trong quá trình cài/merge API-VPS.

## File quan trọng

```text
app.py                          ASGI entrypoint
vps_control/app.py              FastAPI API
vps_control/file_service.py     File Manager an toàn
vps_control/docker_service.py   Docker Manager
vps_control/deploy_service.py   Deploy + rollback project
vps_control/backup_service.py   Backup/restore
vps_control/system_service.py   Monitoring
vps_control/security.py         Auth + rate limit
dashboard/                      SPA
docker-compose.yml              Production container
scripts/install.sh              Cài lần đầu
scripts/activate-auto-deploy.sh Kích hoạt GitHub → VPS một lần
scripts/deploy-vps.sh           Deploy/rollback
scripts/update.sh               Wrapper cập nhật
.github/workflows/ci.yml        CI + smoke test
.github/workflows/deploy-vps.yml SSH auto deploy
```

## Quy trình cho ChatGPT/Codex lần sau

1. Đọc `README.md`.
2. Đọc file này.
3. GitHub `main` là source of truth.
4. Tạo branch, chạy CI, merge PR.
5. Nếu auto deploy chưa kích hoạt, chạy `sudo ./scripts/activate-auto-deploy.sh` một lần trên VPS.
6. Không sửa trực tiếp VPS trừ kích hoạt lần đầu hoặc xử lý sự cố.
