#!/usr/bin/env bash
set -o errexit

if [ "$1" = "web" ]; then
    gunicorn ecoret_backend.wsgi:application \
        --bind 0.0.0.0:$PORT \
        --workers 3 \
        --timeout 120 \
        --access-logfile - \
        --error-logfile -

elif [ "$1" = "worker" ]; then
    celery -A ecoret_backend worker \
        --loglevel=info \
        --concurrency=2

elif [ "$1" = "beat" ]; then
    celery -A ecoret_backend beat \
        --loglevel=info \
        --scheduler django_celery_beat.schedulers:DatabaseScheduler

else
    echo "Unknown service: $1"
    exit 1
fi