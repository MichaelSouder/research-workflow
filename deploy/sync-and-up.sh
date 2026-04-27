#!/usr/bin/env bash
# Sync this repo to a remote host and restart the stack with production compose files.
# Usage:
#   export DEPLOY_SSH='you@lnpiapp.med.umn.edu'
#   export DEPLOY_REMOTE_DIR='~/qualtrics-automation'   # path on the server
#   ./deploy/sync-and-up.sh
#
# Prerequisites: SSH key access, Docker + Docker Compose v2 on the remote host,
# and .env.production created on the server (or synced — see below).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SSH_TARGET="${DEPLOY_SSH:?Set DEPLOY_SSH, e.g. you@lnpiapp.med.umn.edu}"
REMOTE="${DEPLOY_REMOTE_DIR:?Set DEPLOY_REMOTE_DIR, e.g. ~/qualtrics-automation}"

echo "==> Rsync $ROOT -> $SSH_TARGET:$REMOTE"
rsync -avz --delete \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude 'frontend/node_modules' \
  --exclude 'frontend/dist' \
  --exclude '__pycache__' \
  --exclude '.env' \
  --exclude '.env.local' \
  --exclude '.env.production' \
  --exclude 'backup' \
  --exclude '.cursor' \
  "$ROOT/" "$SSH_TARGET:$REMOTE/"

echo "==> Remote: docker compose up"
ssh "$SSH_TARGET" "cd $REMOTE && docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production up -d --build"

echo "==> Done. Open FRONTEND_URL from .env.production (ensure TLS / reverse proxy is configured on the host)."
