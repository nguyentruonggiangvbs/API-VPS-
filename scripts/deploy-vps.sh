#!/bin/bash
set -e

PROJECT_DIR="/opt/api-vps"

cd "$PROJECT_DIR"

echo "Pull latest source"
git pull

echo "Rebuild containers"
docker compose build

echo "Restart services"
docker compose up -d

echo "Deployment completed"
docker ps
