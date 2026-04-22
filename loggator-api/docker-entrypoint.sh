#!/bin/sh
set -e

echo "Starting Loggator API..."
exec uvicorn loggator.main:app --host 0.0.0.0 --port 8000
