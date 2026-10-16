#!/bin/sh
set -eu

PORT="${PORT:-8080}"

echo "=================================================="
echo " Starting Saariv (Early Access Platform)"
echo " Binding to 0.0.0.0:${PORT}"
echo " Health check: GET /health"
echo "=================================================="

exec gunicorn \
  --bind "0.0.0.0:${PORT}" \
  --workers 1 \
  --threads 4 \
  --timeout 60 \
  --access-logfile - \
  --error-logfile - \
  --capture-output \
  app:app
