#!/usr/bin/env bash
# VPS deployment script — run this on your VPS after first-time setup
# Usage: ./scripts/vps-deploy.sh
set -euo pipefail

COMPOSE="docker compose -f docker-compose.vps.yml"

echo "==> Pulling latest images..."
$COMPOSE pull

echo "==> Starting services..."
$COMPOSE up -d

echo "==> Waiting for API health check..."
for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/api/v1/health >/dev/null 2>&1; then
    echo "==> API is healthy"
    break
  fi
  echo "    ...waiting ($i/30)"
  sleep 2
done

echo "==> Done. API running at http://127.0.0.1:8000"
