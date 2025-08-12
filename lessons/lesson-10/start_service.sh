#!/bin/bash
set -euo pipefail

COMPOSE_FILE="../../deploy/docker/docker-compose.yml"

# Detect docker compose command
if docker compose version >/dev/null 2>&1; then
  DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  echo "docker compose/docker-compose is not installed" >&2
  exit 1
fi

echo "Starting services for lesson-10 (API, Dialog, Counter, Redis, Postgres, RabbitMQ, Nginx)"
$DC -f "$COMPOSE_FILE" build | cat
$DC -f "$COMPOSE_FILE" up -d redis postgres rabbitmq dialog-service counter-service monolith nginx | cat

# Wait for health
echo "Waiting for services to be healthy..."
for svc in 8000/health 8002/health 8003/health; do
  url="http://localhost:${svc}"
  for i in {1..60}; do
    code=$(curl -s -o /dev/null -w "%{http_code}" "$url" || true)
    if [ "$code" = "200" ]; then
      echo "OK: $url"
      break
    fi
    sleep 1
    if [ $i -eq 60 ]; then
      echo "Timeout waiting for $url" >&2
      exit 1
    fi
  done
done

echo "Done."

