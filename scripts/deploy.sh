#!/usr/bin/env sh
set -eu

APP_DIR="${APP_DIR:-/opt/media-agent}"
ENV_FILE="${ENV_FILE:-.env.production}"
export ENV_FILE

cd "$APP_DIR"

if [ ! -f "$ENV_FILE" ]; then
  if [ -f ".env.example" ]; then
    cp .env.example "$ENV_FILE"
    echo "Created $APP_DIR/$ENV_FILE from .env.example. Fill real API keys on the server for production publishing."
  else
    echo "Missing $APP_DIR/$ENV_FILE and .env.example"
    exit 1
  fi
fi

compose() {
  docker compose --env-file "$ENV_FILE" -f docker-compose.prod.yml "$@"
}

compose pull
compose up -d
