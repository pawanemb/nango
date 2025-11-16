#!/bin/bash

# Ensure logs directory exists
mkdir -p logs

# Load environment variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Activate virtual environment
source venv/bin/activate

# Start blog generation worker with REDUCED concurrency to prevent resource contention
celery -A app.celery_config worker -Q blog_generation -n blog_generation_worker --concurrency=6 --loglevel=info > logs/celery_blog_generation_worker.log 2>&1 &

# Start image generation worker with LIMITED concurrency (images are resource intensive)
celery -A app.celery_config worker -Q image_generation -n image_generation_worker --concurrency=4 --loglevel=info > logs/celery_image_generation_worker.log 2>&1 &

# Start main worker with REDUCED concurrency
celery -A app.celery_config worker --concurrency=4 --loglevel=info > logs/celery_main_worker.log 2>&1 &

# Start Celery beat scheduler (only one instance)
celery -A app.celery_config beat --loglevel=info > logs/celery_beat.log 2>&1 &

# Keep track of workers
echo "Celery workers started in background with controlled concurrency"
