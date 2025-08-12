#!/bin/bash
set -e

# Включение расширения Citus
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS citus;
EOSQL

echo "Инициализация рабочего узла Citus завершена" 