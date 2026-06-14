"""
Test dataset factory: creates the canonical dataset described in test_template.md.

Summary:
  Authors : 243  (A=137, B=58, C=19, Ш=15, Other=14)
  Books   : 546  (English=459, Ukrainian=87)
  Series  : 98   (C=14, S=62, T=11, Other=11)
  Genres  : 7 leaf genres under 3 parent genres
"""

from library.models import Author, Book, BookSeries, Genre, Language


def create_test_dataset() -> dict:
    """Create the canonical test dataset and return key objects.

    Returns a dict with keys: lang_en, lang_uk, genres (dict), books (list), series (list).
    """
    lang_en, lang_uk, leaf_genres, genres = _create_languages_and_genres()
    _create_authors()
    books = _create_books(lang_en, lang_uk, leaf_genres)
    series = _create_series()
    return {
        'lang_en': lang_en,
        'lang_uk': lang_uk,
        'genres': genres,
        'books': books,
        'series': series,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _create_languages_and_genres() -> tuple[Language, Language, list[Genre], dict[str, Genre]]:
    """Create English and Ukrainian languages plus the 3-parent / 7-leaf genre tree.

    Returns:
        lang_en: the English Language instance.
        lang_uk: the Ukrainian Language instance.
        leaf_genres: ordered list of the 7 leaf Genre instances.
        genres: mapping of code → Genre for all 10 genres (3 parent + 7 leaf).
    """
    lang_en = Language.objects.create(name='English',    code='en')
    lang_uk = Language.objects.create(name='Українська', code='uk')

    sf_fantasy     = Genre.objects.create(name='Science Fiction & Fantasy', code='sf_fantasy')
    myst_thrillers = Genre.objects.create(name='Mysteries & Thrillers',     code='mysteries_thrillers')
    action_adv     = Genre.objects.create(name='Action & Adventure',        code='action_adventure')

    dystopia       = Genre.objects.create(name='Dystopia',         code='dystopia',        parent=sf_fantasy)
    sci_fi         = Genre.objects.create(name='Science Fiction',  code='science_fiction', parent=sf_fantasy)
    fantasy        = Genre.objects.create(name='Fantasy',          code='fantasy',         parent=sf_fantasy)
    mystery        = Genre.objects.create(name='Mystery',          code='mystery',         parent=myst_thrillers)
    thriller       = Genre.objects.create(name='Thriller',         code='thriller',        parent=myst_thrillers)
    adventure      = Genre.objects.create(name='Adventure',        code='adventure',       parent=action_adv)
    nature_animals = Genre.objects.create(name='Nature & Animals', code='nature_animals',  parent=action_adv)

    leaf_genres = [dystopia, sci_fi, fantasy, mystery, thriller, adventure, nature_animals]
    genres = {
        'sf_fantasy':          sf_fantasy,
        'mysteries_thrillers': myst_thrillers,
        'action_adventure':    action_adv,
        'dystopia':            dystopia,
        'science_fiction':     sci_fi,
        'fantasy':             fantasy,
        'mystery':             mystery,
        'thriller':            thriller,
        'adventure':           adventure,
        'nature_animals':      nature_animals,
    }
    return lang_en, lang_uk, leaf_genres, genres


def _create_authors() -> None:
    """Bulk-create 243 authors spread across letter groups A, B, C, Ш, and Other."""
    def _batch(prefix: str, n: int) -> list[Author]:
        return [Author(last_name=f'{prefix}{i + 1}', first_name='') for i in range(n)]

    Author.objects.bulk_create(
        # A group
        _batch('Abak', 21) + _batch('Aban', 39) +   # Ab > Aba: 21 + 39 = 60
        _batch('Abi',  42) + _batch('Aby',   8) +   # Ab: +42 +8 = 110
        _batch('Ac',   11) + _batch('Ad',   16) +   # A: +11 +16 = 137
        # B group
        _batch('Ba',   30) + _batch('Be',   28) +   # B: 30 + 28 = 58
        # single-letter groups
        _batch('C',    19) +                         # C: 19
        _batch('Ш',    15) +                         # Ш: 15
        # Other (non-alpha=3, Z=8, Ї=2, Э=1)
        [Author(last_name='!_1', first_name=''),
         Author(last_name='(_2', first_name=''),
         Author(last_name='+_3', first_name='')] +
        _batch('Z', 8) + _batch('Ї', 2) +
        [Author(last_name='Э1', first_name='')]
    )


def _create_books(lang_en: Language, lang_uk: Language, leaf_genres: list[Genre]) -> list[Book]:
    """Bulk-create 546 books (459 English, 87 Ukrainian) across 7 leaf genres.

    Args:
        lang_en: English Language instance.
        lang_uk: Ukrainian Language instance.
        leaf_genres: ordered list of 7 leaf Genre instances matching GROUPS genre_counts columns.

    Returns:
        List of created Book instances in insertion order.
    """
    # genre_counts order: [dystopia, sci_fi, fantasy, mystery, thriller, adventure, nature_animals]
    # Each row total equals the number of books in that title-prefix group.
    # non-alpha (*) books are split: 12 English + 2 Ukrainian = 14 total.
    GROUPS = [
        ('Alid', lang_en, [4, 3, 3, 4, 3, 3, 3]),   # 23
        ('Alit', lang_en, [5, 5, 5, 5, 5, 5, 4]),   # 34
        ('All',  lang_en, [6, 6, 6, 6, 5, 5, 5]),   # 39
        ('Ana',  lang_en, [6, 6, 6, 6, 6, 6, 5]),   # 41
        ('And',  lang_en, [6, 6, 6, 6, 6, 6, 6]),   # 42
        ('Ar',   lang_en, [7, 6, 6, 6, 6, 6, 6]),   # 43
        ('Bar',  lang_en, [6, 6, 6, 5, 5, 5, 5]),   # 38
        ('Bat',  lang_en, [7, 7, 7, 7, 6, 6, 6]),   # 46
        ('Bl',   lang_en, [6, 6, 6, 6, 6, 6, 6]),   # 42
        ('Bo',   lang_en, [6, 6, 6, 6, 6, 6, 5]),   # 41
        ('M',    lang_en, [7, 6, 6, 6, 6, 6, 6]),   # 43
        ('Пе',   lang_uk, [6, 6, 6, 6, 6, 6, 6]),   # 42 Ukrainian
        ('Пр',   lang_uk, [6, 6, 6, 6, 6, 6, 5]),   # 41 Ukrainian
        # non-alpha (*): English slice
        ('!',    lang_en, [2, 2, 2, 1, 0, 0, 0]),   # 7 English
        ('(',    lang_en, [0, 0, 0, 1, 2, 2, 0]),   # 5 English
        # non-alpha (*): Ukrainian slice — brings total Ukrainian to 42+41+2+2=87
        ('-',    lang_uk, [0, 0, 0, 0, 0, 0, 2]),   # 2 Ukrainian
        ('Q',    lang_en, [1, 1, 1, 1, 1, 1, 1]),   # 7
        ('X',    lang_en, [2, 1, 1, 1, 1, 1, 1]),   # 8
        ('Ю',    lang_uk, [1, 1, 0, 0, 0, 0, 0]),   # 2 Ukrainian
    ]

    book_data = []   # list of (title, language, genre)
    counters: dict[str, int] = {}

    for prefix, lang, genre_counts in GROUPS:
        for genre, count in zip(leaf_genres, genre_counts):
            for _ in range(count):
                n = counters.get(prefix, 0) + 1
                counters[prefix] = n
                book_data.append((f'{prefix}{n}', lang, genre))

    book_objs = [Book(title=title, language=lang) for title, lang, _ in book_data]
    books = Book.objects.bulk_create(book_objs)

    # Assign leaf genres via the auto-created M2M through table
    BookGenre = Book.genres.through
    BookGenre.objects.bulk_create([
        BookGenre(book_id=books[i].pk, genre_id=genre.pk)
        for i, (_, _, genre) in enumerate(book_data)
    ])

    return books


def _create_series() -> list[BookSeries]:
    """Bulk-create 98 book series spread across groups C (14), S (62), T (11), and Other (11).

    Returns:
        List of created BookSeries instances in insertion order.
    """
    def _batch(prefix: str, n: int) -> list[BookSeries]:
        return [BookSeries(name=f'{prefix}{i + 1}') for i in range(n)]

    return BookSeries.objects.bulk_create(
        # C group: Ch=6, Cr=8 → 14
        _batch('Ch',  6) + _batch('Cr',  8) +
        # S group: Sh=6, Sta=28, Ste=26, Sw=2 → 62
        _batch('Sh',  6) + _batch('Sta', 28) + _batch('Ste', 26) + _batch('Sw', 2) +
        # T group: 11
        _batch('T',  11) +
        # Other: non-alpha=4, N=4, В=3 → 11
        [BookSeries(name=f'({i + 1}') for i in range(2)] +
        [BookSeries(name=f'_{i + 1}') for i in range(2)] +
        _batch('N', 4) + _batch('В', 3)
    )
