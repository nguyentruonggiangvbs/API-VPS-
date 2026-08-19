# API-VPS Deployment Guide

## Architecture

```
Developer / ChatGPT / Codex
          |
          v
       GitHub
          |
          v
    VPS Hostinger
          |
          v
 Docker Compose Services
```

## Current VPS

- Project path: `/opt/api-vps`
- API port: `9000`
- Dashboard: `/dashboard/`
- Runtime: Docker Compose

## Deploy manually

```bash
cd /opt/api-vps

git pull

docker compose down

docker compose up -d --build
```

## Verify

```bash
docker ps
curl http://localhost:9000
```

Expected:

```json
{"status":"running","service":"api-vps"}
```

## Update workflow

1. Update source code in GitHub.
2. Commit changes.
3. VPS pulls latest version.
4. Docker rebuilds containers.

## Rollback

```bash
git log
git checkout <commit>
docker compose up -d --build
```

## Future modules

- Automatic GitHub webhook deploy
- File Manager
- Docker Manager
- Web Terminal
- Backup Manager
- Monitoring realtime
