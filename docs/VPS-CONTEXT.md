# API-VPS Project Context

## Mục tiêu

API-VPS là hệ thống quản lý VPS thông qua web dashboard. Mục tiêu là để ChatGPT/Codex có thể đọc tài liệu dự án và tiếp tục phát triển mà không cần tìm lại lịch sử thao tác.

## Kiến trúc hiện tại

```
ChatGPT / Codex
        |
        v
GitHub API-VPS Repository
        |
        v
VPS Hostinger
        |
        +-- Docker
        |    +-- api-vps
        |    +-- camera-pc
        |
        +-- Dashboard Web
```

## VPS hiện tại

- API service chạy port: `9000`
- Dashboard URL:
  - `http://SERVER_IP:9000/dashboard/`

## Các chức năng đã hoàn thành

### API Backend

- FastAPI backend
- Health check
- System info
- Docker status
- Docker restart
- Docker logs

### Dashboard

Đã có:

- CPU monitoring
- RAM monitoring
- Disk monitoring
- Docker container list

## Cấu trúc mong muốn tiếp tục phát triển

```
Dashboard
 |
 +-- Overview
 |
 +-- Docker Manager
 |
 +-- File Manager
 |
 +-- Terminal Web
 |
 +-- Logs Center
 |
 +-- Backup Manager
 |
 +-- Deploy Manager
```

## Quy trình triển khai chuẩn

Sau khi cập nhật code:

```bash
cd /opt/api-vps

docker compose down

docker compose up -d --build
```

Kiểm tra:

```bash
docker ps
curl http://localhost:9000
```

## Quy tắc phát triển

- Không sửa trực tiếp trên VPS nếu không cần thiết.
- GitHub là source chính.
- Mọi thay đổi cần commit rõ ràng.
- Dashboard và API phải tương thích.

## Kế hoạch tiếp theo

1. File Manager thật.
2. Docker Manager đầy đủ.
3. Deploy tự động từ GitHub.
4. Backup VPS.
5. Monitoring realtime.
6. Webhook GitHub -> VPS auto deploy.

## Lưu ý cho ChatGPT/Codex

Khi tiếp tục dự án:

- Đọc file này trước.
- Giữ nguyên kiến trúc Docker + FastAPI.
- Ưu tiên cập nhật GitHub trước, sau đó deploy VPS.
