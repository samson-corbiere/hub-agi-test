#!/bin/sh
# Creates the database used by pytest, next to the dev database.
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -c "CREATE DATABASE ${POSTGRES_DB}_test OWNER \"$POSTGRES_USER\";"
