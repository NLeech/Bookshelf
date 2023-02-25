from django.db import models
from django.conf import settings


class Language(models.Model):
    """
    Language and language code (ISO 639-1 Code)

    """

    name = models.CharField(
        max_length=100,
        verbose_name='Language',
        help_text='English name of Language'
    )
    code = models.CharField(
        max_length=2,
        primary_key=True,
        verbose_name='Language  code',
        help_text='Language ISO 639-1 Code'
    )

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Languages'


class Name(models.Model):
    """
    Names for authors (pseudonyms, translated names, names in the different first name and surname order, etc.)
    Book titles (translated titles, different variants of translation, etc.)
    Series names (translated titles, different variants of translation, etc.)

    """

    name = models.CharField(max_length=255, verbose_name='Name')
    language = models.ForeignKey(
        'Language',
        on_delete=models.CASCADE,
        related_name='name',
        verbose_name='Language',
    )

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Names'


class Author(models.Model):
    name = models.CharField(max_length=255, verbose_name='Name')
