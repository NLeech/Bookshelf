#!/bin/bash

# abort on error
set -e

cd /Bookshelf/bookshelf

python manage.py migrate
python manage.py collectstatic --no-input
python manage.py initadmin

echo "Starting celery beat"
celery -A bookshelf beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler &

echo "Starting celery worker"
celery -A bookshelf worker -l INFO -c 1 &

exec gunicorn --timeout 60 --bind 0.0.0.0:8080 -w 3 bookshelf.wsgi