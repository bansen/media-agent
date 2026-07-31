#!/usr/bin/env bash
set -euo pipefail

: "${DEPLOY_HOST:?DEPLOY_HOST is required}"
: "${DEPLOY_USER:?DEPLOY_USER is required}"
: "${DEPLOY_PATH:=/opt/media-agent}"
: "${REPO_URL:?REPO_URL is required}"
: "${ENV_FILE:=.env.production}"

ssh "${DEPLOY_USER}@${DEPLOY_HOST}" "set -euo pipefail
  if [ ! -d '${DEPLOY_PATH}/.git' ]; then
    sudo mkdir -p '${DEPLOY_PATH}'
    sudo chown '${DEPLOY_USER}' '${DEPLOY_PATH}'
    git clone '${REPO_URL}' '${DEPLOY_PATH}'
  else
    cd '${DEPLOY_PATH}'
    git pull --ff-only
  fi
  cd '${DEPLOY_PATH}'
  if [ ! -f '${ENV_FILE}' ]; then
    cp .env.example '${ENV_FILE}'
    echo 'Created ${ENV_FILE} from .env.example. Fill it before starting the service.' >&2
    exit 1
  fi
  ENV_FILE='${ENV_FILE}' docker compose --env-file '${ENV_FILE}' -f docker-compose.prod.yml up -d app
"
