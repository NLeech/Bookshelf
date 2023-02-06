#!/bin/bash

cd bookshelf

python manage.py migrate &&
python manage.py collectstatic --noinput

python manage.py createsuperuser --noinput --username admin --email admin@example.com

python manage.py runserver 0.0.0.0:80
