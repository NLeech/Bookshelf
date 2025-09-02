from django.db import models

from library.models import Author


class FlibustaGenre(models.Model):
    """
    Genre from Flibusta
    """
    genre_code = models.CharField(max_length=100, unique=True, verbose_name='Genre code')
    genre_desc = models.CharField(max_length=200, verbose_name='Genre description')

    # name of the main genre, for example, "Detective" for "Detective-Adventure"
    genre_meta = models.CharField(max_length=100, verbose_name='Genre meta')

    def __str__(self):
        return f'({self.id}) {self.genre_code}, {self.genre_desc}'


class FlibustaAuthor(models.Model):
    """
    Author from Flibusta
    """
    first_name = models.CharField(max_length=100, blank=True, default='', verbose_name='First name')
    middle_name = models.CharField(max_length=100, blank=True, default='', verbose_name='Middle name')
    last_name = models.CharField(max_length=100, blank=True, default='', verbose_name='Last name')
    nickname = models.CharField(max_length=50, blank=True, default='', verbose_name='Nickname')
    email = models.CharField(max_length=255, blank=True, default='', verbose_name='E-mail')
    homepage = models.CharField(max_length=255, blank=True, default='', verbose_name='Homepage')
    main_author = models.ForeignKey('self', null=True, blank=True, related_name='different_names',
                                    on_delete=models.CASCADE, verbose_name='Main author')

    # linked author in the local library, for the future synchronization
    library_author = models.ForeignKey(Author, null=True, blank=True, related_name='library_authors',
                                       on_delete=models.CASCADE, verbose_name='Linked library author')

    def __str__(self):
        return f'({self.id}) {self.last_name}, {self.first_name}, {self.middle_name} ({self.main_author})'


