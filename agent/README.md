# VPS Deploy Agent

## Mục đích

Agent chạy trên VPS để nhận lệnh deploy từ GitHub.

## Luồng hoạt động

GitHub Push

↓

Webhook

↓

VPS Deploy Agent

↓

```bash
git pull
docker compose up -d --build
```

## Cấu hình

Environment:

```env
DEPLOY_SECRET=your-secret
PROJECT_PATH=/opt/api-vps
```

## API

Health:

```
GET /health
```

Deploy:

```
POST /deploy
Header:
x-deploy-secret: your-secret
```
