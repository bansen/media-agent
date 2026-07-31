#!/usr/bin/env sh
set -eu

APP_DIR="${APP_DIR:-/opt/media-agent}"
ENV_FILE="${ENV_FILE:-.env.production}"
export ENV_FILE

cd "$APP_DIR"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $APP_DIR/$ENV_FILE"
  exit 1
fi

compose() {
  docker compose --env-file "$ENV_FILE" -f docker-compose.prod.yml "$@"
}

compose pull app
compose up -d app
