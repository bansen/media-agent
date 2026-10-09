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

env_value() {
  key="$1"
  grep -E "^${key}=" "$ENV_FILE" | tail -n 1 | cut -d= -f2-
}

if [ "$(env_value WEBSEARCH_MCP_ENABLED)" = "true" ] && [ -z "$(env_value TAVILY_API_KEY)" ]; then
  echo "Missing TAVILY_API_KEY in $APP_DIR/$ENV_FILE while WEBSEARCH_MCP_ENABLED=true"
  exit 1
fi

compose() {
  docker compose --env-file "$ENV_FILE" -f docker-compose.prod.yml "$@"
}

compose pull
compose up -d --wait --wait-timeout 120

# Image-only cleanup: Docker preserves images referenced by any container.
echo "Deployment started successfully. Removing all unused server images."
docker image prune --all --force
