import re

from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill


class BaseModel(models.Model):
    created_at = models.DateTimeField(db_index=True, default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Language(models.Model):
    """
    Language and language code (ISO 639-1 Code)
    """

    name = models.CharField(
        max_length=100,
        verbose_name='Language',
        help_text='Language name in English'
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


class GenreName(BaseModel):
    """
    Genre alternative names or translations in different languages
    """
    name = models.CharField(max_length=250, verbose_name='Genre name')
    language = models.ForeignKey(Language, on_delete=models.PROTECT, related_name='genre_names',
                                 verbose_name='Language')

    genre = models.ForeignKey('Genre', on_delete=models.CASCADE, related_name='names', verbose_name='Genre')

    def __str__(self):
        return f'{self.name}'

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Genre names'


class Genre(BaseModel):
    """
    Book genres, with recursive relationship
    """

    name = models.CharField(max_length=250, verbose_name='Genre name')
    code = models.CharField(max_length=150, null=False, blank=False, unique=True, verbose_name='Genre code')
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='subgenres',
        verbose_name='Parent genre'
    )

    def clean_fields(self, exclude=None):
        super().clean_fields(exclude=exclude)
        if self.parent is not None and self.id == self.parent.id:
            raise ValidationError('A genre can’t be a parent of itself.')

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Genres'


class BookSeriesName(BaseModel):
    """
    Series names (translated titles, different translation variants, etc.)
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


class BookSeries(BaseModel):
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


class Author(BaseModel):
    """
    Author names, including pseudonyms, translated names, etc.
    """

    first_name = models.CharField(max_length=255, blank=True, verbose_name='First name')
    middle_name = models.CharField(max_length=255, blank=True, verbose_name='Middle name')
    last_name = models.CharField(max_length=255, verbose_name='Last name')

    nickname = models.CharField(max_length=50, blank=True, default='', verbose_name='Nickname')
    email = models.CharField(max_length=255, blank=True, default='', verbose_name='E-mail')
    homepage = models.CharField(max_length=255, blank=True, default='', verbose_name='Homepage')

    main_author = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='different_names',
        verbose_name='Main author'
    )

    @staticmethod
    def _get_author_full_name(first_name: str, middle_name: str, last_name: str) -> str:
        """Construct the full name of an author.

        Args:
            first_name: The first name of the author.
            middle_name: The middle name of the author.
            last_name: The last name of the author.

        Returns:
            The full name in the format 'Last, First Middle'.
        """
        full_name = f'{last_name}, {first_name} {middle_name}'.strip()
        # remove duplicate spaces if the first name is empty
        return re.sub(r' +', ' ', full_name)

    @property
    def full_name(self):
        return self._get_author_full_name(self.first_name, self.middle_name, self.last_name)

    def clean_fields(self, exclude=None):
        super().clean_fields(exclude=exclude)

        # Author can't be linked with itself
        if self.main_author is not None and self.id == self.main_author.id:
            raise ValidationError('An author record cannot reference itself.')

        # An author cannot be linked to another who is already linked to the main author.
        # The hierarchy is limited to two levels: the main author and their alternative names.
        if self.main_author is not None and self.main_author.main_author is not None:
            raise ValidationError('An author cannot be linked to another who is already linked to the main author.')

    def __str__(self):
        return f'{self.full_name}'

    class Meta:
        ordering = ['last_name', 'first_name', 'middle_name']
        verbose_name_plural = 'Authors'
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'last_name',
                    'first_name',
                    'middle_name',
                    'main_author',
                ],
                name='unique_author'
            ),
        ]


class BookSeriesLink(BaseModel):
    """
    Through model for Book-Series relationship to store sequence number
    """
    book = models.ForeignKey('Book', on_delete=models.CASCADE)
    series = models.ForeignKey('BookSeries', on_delete=models.CASCADE)
    sequence_number = models.IntegerField(default=0, verbose_name='Sequence Number')

    def __str__(self):
        return str(self.book)

    class Meta:
        verbose_name = 'Book Series Link'
        verbose_name_plural = 'Book Series Links'
        unique_together = ('book', 'series')

    
class Book(BaseModel):
    """
    Book with all related information
    """

    title = models.CharField(max_length=255, verbose_name='Title')
    description = models.TextField(null=False, blank=True, default='', verbose_name='Description')
    language = models.ForeignKey('Language', on_delete=models.RESTRICT, related_name='books',
                                 verbose_name='Language')
    isbn = models.DecimalField(max_digits=13, decimal_places=0, default=0, verbose_name='ISBN')
    file = models.FileField(upload_to='books/', null=True, blank=True, verbose_name='Book File')
    size = models.PositiveIntegerField(default=0, verbose_name='File size (bytes)')
    file_type = models.CharField(max_length=20, blank=True, verbose_name='File type')

    cover = models.ImageField(upload_to='covers/', null=True, blank=True, verbose_name='Cover')
    cover_preview = ImageSpecField(source='cover',
                                      processors=[ResizeToFill(100, 150)],
                                      format='JPEG',
                                      options={'quality': 80})

    authors = models.ManyToManyField('Author', related_name='books', verbose_name='Authors')
    series = models.ManyToManyField('BookSeries', through='BookSeriesLink', related_name='books', verbose_name='Series')
    genres = models.ManyToManyField('Genre', related_name='books', verbose_name='Genres')

    def __str__(self):
        return self.title

    @property
    def size_str(self) -> str:
        """Return the file size in a human-readable format.

        Format:
        - XXX B (if size < 1 KB)
        - XX.XX KB (if size < 1 MB)
        - XX.XX MB (if size >= 1 MB)
        Using binary base (1024).

        Returns:
            A string representing the human-readable file size.
        """
        if self.size < 1024:
            return f'{self.size} B'
        elif self.size < 1024 * 1024:
            size_kb = self.size / 1024
            return f'{size_kb:.2f} KB'
        else:
            size_mb = self.size / (1024 * 1024)
            return f'{size_mb:.2f} MB'
