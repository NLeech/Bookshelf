import os.path

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):

    def handle(self, *args, **options):

        if get_user_model().objects.count() == 0:
            username = 'admin'
            email = 'admin@example.com'
            password = os.environ.get('SUPERUSER_PASSWORD')
            print(f'Creating account for {username} ({email})')
            admin = get_user_model().objects.create_superuser(email=email, username=username, password=password)
            admin.registration_complete = True
            admin.save()
