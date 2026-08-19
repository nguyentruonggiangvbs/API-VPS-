# API-VPS Auto Deploy Architecture

## Mục tiêu

Thiết lập luồng phát triển:

```
ChatGPT / Codex
      |
      v
GitHub Repository
      |
      v
GitHub Actions
      |
      v
VPS Hostinger
      |
      v
Docker Compose
```

## Quy trình cập nhật

1. Code được cập nhật trên GitHub.
2. GitHub Actions kiểm tra build.
3. VPS nhận lệnh deploy.
4. VPS thực hiện:

```bash
git pull
docker compose build
docker compose up -d
```

## VPS hiện tại

- Project path: `/opt/api-vps`
- API port: `9000`
- Dashboard: `/dashboard/`

## Nguyên tắc

- GitHub là source chính.
- Không sửa trực tiếp VPS nếu không cần.
- Mọi thay đổi phải có commit.
- Backup trước khi deploy production.

## Module kế hoạch

- Dashboard Monitoring
- Docker Manager
- File Manager
- Web Terminal
- Backup Manager
- Deploy Agent
