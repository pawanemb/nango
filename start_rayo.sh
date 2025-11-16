#!/bin/bash
set -e

APP_DIR="/home/pawan_patra/Rayo-backend-pawan"
LOG_DIR="$APP_DIR/logs"
GUNICORN_LOG_DIR="/home/pawan_patra/Rayo-backend-pawan/gunicorn_logs"
VENV="$APP_DIR/venv"

# Create necessary directories
mkdir -p "$LOG_DIR"
mkdir -p "$GUNICORN_LOG_DIR"

# Load environment variables
if [ -f "$APP_DIR/.env" ]; then
    export $(grep -v '^#' "$APP_DIR/.env" | grep -v '^[[:space:]]*$' | xargs -d '\n')
elif [ -f "$APP_DIR/config_template.env" ]; then
    export $(grep -v '^#' "$APP_DIR/config_template.env" | grep -v '^[[:space:]]*$' | xargs -d '\n')
fi

# Activate virtual environment
source "$VENV/bin/activate"

# Start Gunicorn with FastAPI
CPU_CORES=$(nproc)
WORKERS=$((CPU_CORES * 2 + 1))  # standard Gunicorn formula
exec "$VENV/bin/gunicorn" \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers $WORKERS \
    --timeout 120 \
    --graceful-timeout 15 \
    --max-requests 500 \
    --max-requests-jitter 50 \
    --log-level info \
    --access-logfile "$GUNICORN_LOG_DIR/access.log" \
    --error-logfile "$GUNICORN_LOG_DIR/error.log" \
    --worker-tmp-dir /dev/shm \
    --worker-connections 2000 \
    --keep-alive 5 \
    --bind 0.0.0.0:8000 \
    main:app
