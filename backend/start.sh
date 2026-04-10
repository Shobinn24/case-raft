#!/bin/bash
set -e

echo "=== Case Raft Startup ==="
echo "PORT=$PORT"
echo "FLASK_APP=$FLASK_APP"
echo "DATABASE_URL is set: $([ -n "$DATABASE_URL" ] && echo 'yes' || echo 'NO')"

echo "=== Running database migrations ==="
flask db upgrade 2>&1
echo "=== Migrations complete ==="

echo "=== Starting Gunicorn on 0.0.0.0:$PORT ==="
exec gunicorn run:app \
    --bind "0.0.0.0:$PORT" \
    --workers 2 \
    --threads 4 \
    --timeout 120 \
    --preload \
    --log-level info \
    --capture-output \
    --access-logfile - \
    --error-logfile -
