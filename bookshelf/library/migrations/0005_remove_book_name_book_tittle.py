# Generated by Django 4.1.6 on 2023-02-27 15:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('library', '0004_book'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='book',
            name='name',
        ),
        migrations.AddField(
            model_name='book',
            name='tittle',
            field=models.CharField(default=11, max_length=255, verbose_name='Tittle'),
            preserve_default=False,
        ),
    ]
