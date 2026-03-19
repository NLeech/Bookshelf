#!/bin/bash

# abort on error
set -e

cd /Bookshelf/bookshelf

python manage.py migrate
python manage.py collectstatic --no-input
python manage.py initadmin

exec gunicorn --timeout 60 --bind 0.0.0.0:8080 -w 3 bookshelf.wsgi