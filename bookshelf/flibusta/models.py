from django.db import models


class FlibustaAuthor(models.Model):
    """
    Mirror of 'libavtorname' table.
    """
    first_name = models.CharField(max_length=99, blank=True, default='', verbose_name='First Name')
    middle_name = models.CharField(max_length=99, blank=True, default='', verbose_name='Middle Name')
    last_name = models.CharField(max_length=99, blank=True, default='', verbose_name='Last Name')
    nickname = models.CharField(max_length=33, blank=True, default='', verbose_name='Nickname')
    uid = models.IntegerField(default=0, db_index=True, verbose_name='User ID')
    email = models.CharField(max_length=255, blank=True, default='', db_index=True, verbose_name='Email')
    homepage = models.CharField(max_length=255, blank=True, default='', db_index=True, verbose_name='Homepage')
    gender = models.CharField(max_length=1, blank=True, default='', verbose_name='Gender')
    master_id = models.IntegerField(default=0, db_index=True, verbose_name='Master ID')

    def __str__(self):
        return f"{self.last_name} {self.first_name} {self.middle_name}".strip() or self.nickname or f"Author {self.id}"

    class Meta:
        verbose_name = 'Flibusta Author'
        verbose_name_plural = 'Flibusta Authors'


class FlibustaGenre(models.Model):
    """
    Mirror of 'libgenrelist' table.
    """
    genre_code = models.CharField(max_length=45, unique=True, verbose_name='Genre Code')
    genre_desc = models.CharField(max_length=99, blank=True, default='', verbose_name='Description')
    genre_meta = models.CharField(max_length=45, blank=True, default='', db_index=True, verbose_name='Meta Genre')

    def __str__(self):
        return self.genre_code

    class Meta:
        verbose_name = 'Flibusta Genre'
        verbose_name_plural = 'Flibusta Genres'


class FlibustaSequence(models.Model):
    """
    Mirror of 'libseqname' table.
    """
    name = models.CharField(max_length=254, unique=True, verbose_name='Sequence Name')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Flibusta Sequence'
        verbose_name_plural = 'Flibusta Sequences'


class FlibustaBook(models.Model):
    """
    Mirror of 'libbook' table.
    """
    file_size = models.PositiveIntegerField(default=0, db_index=True, verbose_name='File Size')
    time = models.DateTimeField(auto_now_add=True, verbose_name='Time Added')
    title = models.CharField(max_length=254, blank=True, default='', db_index=True, verbose_name='Title')
    title1 = models.CharField(max_length=254, blank=True, default='', db_index=True, verbose_name='Title (Alt)')
    lang = models.CharField(max_length=3, blank=True, default='ru', db_index=True, verbose_name='Language')
    lang_ex = models.PositiveSmallIntegerField(default=0, verbose_name='Language Extended')
    src_lang = models.CharField(max_length=3, blank=True, default='', verbose_name='Source Language')
    file_type = models.CharField(max_length=4, blank=True, default='', db_index=True, verbose_name='File Type')
    encoding = models.CharField(max_length=32, blank=True, default='', verbose_name='Encoding')
    year = models.SmallIntegerField(default=0, db_index=True, verbose_name='Year')
    deleted = models.CharField(max_length=1, default='0', db_index=True, verbose_name='Deleted')
    ver = models.CharField(max_length=8, blank=True, default='', verbose_name='Version')
    file_author = models.CharField(max_length=64, blank=True, default='', db_index=True, verbose_name='File Author')
    n = models.PositiveIntegerField(default=0, db_index=True, verbose_name='N')
    keywords = models.CharField(max_length=255, blank=True, default='', verbose_name='Keywords')
    md5 = models.CharField(max_length=32, unique=True, verbose_name='MD5 Hash')
    modified = models.DateTimeField(auto_now=True, verbose_name='Modified')
    pmd5 = models.CharField(max_length=32, blank=True, default='', verbose_name='PMD5')
    info_code = models.PositiveSmallIntegerField(default=0, verbose_name='Info Code')
    pages = models.PositiveIntegerField(default=0, verbose_name='Pages')
    chars = models.PositiveIntegerField(default=0, verbose_name='Chars')

    # Relationships
    authors = models.ManyToManyField(FlibustaAuthor, through='FlibustaBookAuthor', related_name='books', verbose_name='Authors')
    genres = models.ManyToManyField(FlibustaGenre, through='FlibustaBookGenre', related_name='books', verbose_name='Genres')
    sequences = models.ManyToManyField(FlibustaSequence, through='FlibustaBookSequence', related_name='books', verbose_name='Sequences')

    def __str__(self):
        return self.title or f"Book {self.id}"

    class Meta:
        verbose_name = 'Flibusta Book'
        verbose_name_plural = 'Flibusta Books'


class FlibustaBookAuthor(models.Model):
    """
    Through model for Book-Author relationship (libavtor).
    """
    book = models.ForeignKey(FlibustaBook, on_delete=models.CASCADE)
    author = models.ForeignKey(FlibustaAuthor, on_delete=models.CASCADE)
    pos = models.PositiveSmallIntegerField(default=0, verbose_name='Position')

    class Meta:
        verbose_name = 'Flibusta Book-Author Link'
        verbose_name_plural = 'Flibusta Book-Author Links'
        unique_together = ('book', 'author')


class FlibustaBookGenre(models.Model):
    """
    Through model for Book-Genre relationship (libgenre).
    """
    book = models.ForeignKey(FlibustaBook, on_delete=models.CASCADE)
    genre = models.ForeignKey(FlibustaGenre, on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Flibusta Book-Genre Link'
        verbose_name_plural = 'Flibusta Book-Genre Links'
        unique_together = ('book', 'genre')


class FlibustaBookSequence(models.Model):
    """
    Through model for Book-Sequence relationship (libseq).
    """
    book = models.ForeignKey(FlibustaBook, on_delete=models.CASCADE)
    sequence = models.ForeignKey(FlibustaSequence, on_delete=models.CASCADE)
    seq_numb = models.IntegerField(default=0, verbose_name='Sequence Number')
    level = models.PositiveSmallIntegerField(default=0, verbose_name='Level')
    type = models.PositiveSmallIntegerField(default=0, verbose_name='Type')

    class Meta:
        verbose_name = 'Flibusta Book-Sequence Link'
        verbose_name_plural = 'Flibusta Book-Sequence Links'
        unique_together = ('book', 'sequence')


class FlibustaJoinedBook(models.Model):
    """
    Mirror of 'libjoinedbooks' table.
    """
    time = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Time')
    bad_id = models.IntegerField(unique=True, verbose_name='Bad Book ID')
    good_id = models.IntegerField(db_index=True, verbose_name='Good Book ID')
    real_id = models.IntegerField(null=True, blank=True, db_index=True, verbose_name='Real ID')

    def __str__(self):
        return f"{self.bad_id} -> {self.good_id}"

    class Meta:
        verbose_name = 'Flibusta Joined Book'
        verbose_name_plural = 'Flibusta Joined Books'
