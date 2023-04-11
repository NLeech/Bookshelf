# Generated by Django 4.1.7 on 2023-04-11 10:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('library', '0001_initial'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='author',
            name='unique_author',
        ),
        migrations.AddConstraint(
            model_name='author',
            constraint=models.UniqueConstraint(fields=('last_name', 'first_name', 'middle_name', 'main_author'), name='unique_author'),
        ),
    ]
