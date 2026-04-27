#!/usr/bin/env bash
# Build images locally, tag for a registry, push, then pull and restart on the remote host.
# Use when the server should not build images (no build context on production).
#
# Usage:
#   export REGISTRY='registry.lnpiapp.med.umn.edu/research-workflow'   # no trailing slash
#   export DEPLOY_SSH='you@lnpiapp.med.umn.edu'
#   export DEPLOY_REMOTE_DIR='~/qualtrics-automation'
#   ./deploy/push-images.sh
#
# On first use, docker login $REGISTRY (or your org's registry credentials).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REGISTRY="${REGISTRY:?Set REGISTRY, e.g. ghcr.io/yourorg/research-workflow}"
TAG="${TAG:-$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo latest)}"
SSH_TARGET="${DEPLOY_SSH:?Set DEPLOY_SSH}"
REMOTE="${DEPLOY_REMOTE_DIR:?Set DEPLOY_REMOTE_DIR}"

export BACKEND_IMAGE="$REGISTRY/backend:$TAG"
export FRONTEND_IMAGE="$REGISTRY/frontend:$TAG"

cd "$ROOT"

echo "==> Build and push $TAG"
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
docker push "$BACKEND_IMAGE"
docker push "$FRONTEND_IMAGE"

echo "==> Rsync compose files (stack definition only)"
rsync -avz \
  "$ROOT/docker-compose.yml" \
  "$ROOT/docker-compose.prod.yml" \
  "$SSH_TARGET:$REMOTE/"

echo "==> Remote: pull images and up"
ssh "$SSH_TARGET" "cd $REMOTE && \
  BACKEND_IMAGE=$BACKEND_IMAGE FRONTEND_IMAGE=$FRONTEND_IMAGE \
  docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production pull && \
  BACKEND_IMAGE=$BACKEND_IMAGE FRONTEND_IMAGE=$FRONTEND_IMAGE \
  docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production up -d"

echo "==> Deployed tag $TAG"
