#!/bin/sh
set -e

# If arguments were passed (e.g. from 'migrate' service), execute them directly
if [ "$#" -gt 0 ]; then
  exec "$@"
fi

echo "Starting Loggator API..."
exec uvicorn loggator.main:app --host 0.0.0.0 --port 8000
