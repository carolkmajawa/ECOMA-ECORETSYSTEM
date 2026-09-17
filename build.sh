#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

# Only run migrations and collectstatic on the web service.
# Workers/beat share the same DB, so running it on all three causes race conditions.
if [ "$RENDER_SERVICE_TYPE" = "web" ]; then
  python manage.py migrate --no-input
  python manage.py collectstatic --no-input
fi