#!/bin/bash
set -euo pipefail

COMPOSE_FILE="../../deploy/docker/docker-compose.yml"

echo "Stopping services for lesson-10"
docker compose -f "$COMPOSE_FILE" down --remove-orphans | cat
echo "Done."

