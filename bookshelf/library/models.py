from django.db import models
from django.core.exceptions import ValidationError
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

    def __str__(self):
        return self.code

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Languages'


class Genre(models.Model):
    """
    Book genres, with recursive relationship

    """
    name = models.CharField(max_length=255, verbose_name='Genre name')
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='subgenres',
        verbose_name='Parent genre'
    )

    code = models.IntegerField(null=False, unique=True, verbose_name='Genre code')

    def clean_fields(self, exclude=None):
        super().clean_fields(exclude=exclude)
        # Genre can't be a parent for itself
        if self.parent is not None and self.id == self.parent.id:
            raise ValidationError('Genre can`t be a parent for itself')

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Genres'


class BookSeriesName(models.Model):
    """
    Series names (translated names, different variants of translation, etc.)

    """
    name = models.CharField(max_length=255, verbose_name='Series name')
    series = models.ForeignKey(
        'BookSeries',
        on_delete=models.CASCADE,
        related_name='different_names',
        verbose_name='Series'
    )
    language = models.ForeignKey(
        'Language',
        on_delete=models.RESTRICT,
        verbose_name='Language',
    )

    def __str__(self):
        return f'{self.name} ({self.series})'

    class Meta:
        ordering = ['series', 'name']
        verbose_name_plural = 'Series names'
        constraints = [
            models.UniqueConstraint(fields=['name', 'series', 'language'], name='unique_series_name'),
        ]


class BookSeries(models.Model):
    """
    Book series, with recursive relationship

    """
    name = models.CharField(max_length=255, verbose_name='Series name')
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='subseries',
        verbose_name='Parent series'
    )

    def __str__(self):
        return self.name

    def clean_fields(self, exclude=None):
        super().clean_fields(exclude=exclude)
        # Series can't be a parent for itself
        if self.parent is not None and self.id == self.parent.id:
            raise ValidationError('Series can`t be a parent for itself')

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Series'


class AuthorName(models.Model):
    """
    Author names (pseudonyms, translated names, names in the different first name and surname order, etc.)

    """
    name = models.CharField(max_length=255, verbose_name='Author name')
    author = models.ForeignKey(
        'Author',
        on_delete=models.CASCADE,
        related_name='different_names',
        verbose_name='Author'
    )
    language = models.ForeignKey(
        'Language',
        on_delete=models.RESTRICT,
        verbose_name='Language',
    )

    def __str__(self):
        return f'{self.name} ({self.author})'

    class Meta:
        ordering = ['author', 'name']
        verbose_name_plural = 'Author names'
        constraints = [
            models.UniqueConstraint(fields=['name', 'author', 'language'], name='unique_author_name'),
        ]


class Author(models.Model):
    name = models.CharField(max_length=255, verbose_name='Author name')

    def __str__(self):
        return self.name


class Book(models.Model):
    tittle = models.CharField(max_length=255, verbose_name='Tittle')
    annotation = models.TextField(null=False, blank=True, default='', verbose_name='Annotation')
    language = models.ForeignKey('Language', on_delete=models.RESTRICT, related_name='books', verbose_name='Language')

    authors = models.ManyToManyField('Author', related_name='books', verbose_name='Authors')
    series = models.ManyToManyField('BookSeries', related_name='books', verbose_name='Series')
    genres = models.ManyToManyField('Genre', related_name='books', verbose_name='Genres')
