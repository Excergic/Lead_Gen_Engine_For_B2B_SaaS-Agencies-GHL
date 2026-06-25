#!/usr/bin/env bash
# Remote production deploy — run on the VPS (also invoked from GitHub Actions over SSH).
#
# Expects:
#   - docker-compose.vps.yml and .env in the deploy directory
#   - optional GHCR_TOKEN + GITHUB_OWNER for private image pulls
#
# Usage (on VPS):
#   ./scripts/remote-deploy.sh
#
# Usage (from CI):
#   GHCR_TOKEN=... GITHUB_OWNER=excergic VPS_DEPLOY_PATH=~/lead_gen_workflow ./scripts/remote-deploy.sh
set -euo pipefail

DEPLOY_PATH="${VPS_DEPLOY_PATH:-$(cd "$(dirname "$0")/.." && pwd)}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.vps.yml}"
GITHUB_OWNER="${GITHUB_OWNER:-excergic}"

cd "$DEPLOY_PATH"

if [ -d .git ]; then
  echo "==> Updating deploy files from git..."
  git fetch origin main 2>/dev/null || true
  git checkout main 2>/dev/null || true
  git pull origin main 2>/dev/null || echo "    (git pull skipped — continuing with existing files)"
fi

if [ -n "${GHCR_TOKEN:-}" ]; then
  echo "==> Logging in to GHCR..."
  echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GITHUB_OWNER" --password-stdin
fi

echo "==> Pulling latest API image..."
docker compose -f "$COMPOSE_FILE" pull

echo "==> Starting services..."
docker compose -f "$COMPOSE_FILE" up -d

echo "==> Waiting for API health check..."
for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/api/v1/health >/dev/null 2>&1; then
    echo "==> API is healthy"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "ERROR: API did not become healthy in time"
    docker compose -f "$COMPOSE_FILE" logs --tail=50 api || true
    exit 1
  fi
  echo "    ...waiting ($i/30)"
  sleep 2
done

echo "==> Running database migrations..."
docker compose -f "$COMPOSE_FILE" run --rm api python scripts/run_migrations.py

if [ -n "${GHCR_TOKEN:-}" ]; then
  docker logout ghcr.io 2>/dev/null || true
fi

echo "==> Deploy complete"
