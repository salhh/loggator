#!/bin/sh
set -e

echo "Running Alembic migrations..."
alembic upgrade head

echo "Starting Loggator API..."
exec uvicorn loggator.main:app --host 0.0.0.0 --port 8000
