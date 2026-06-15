"""
Test dataset factory: creates the canonical dataset described in test_template.md.

Summary:
  Authors : 255  (A=137, B=58, C=19, Ш=15, 0-9=12, Other=14)
  Books   : 560  (English=473, Ukrainian=87)
  Series  : 148  (C=54, S=62, T=11, 0-9=10, Other=11)
  Genres  : 7 leaf genres under 3 parent genres

Relationships added to support OPDS detail-view tests:
  Book→Author  : every book has exactly 1 author (round-robin over all 255 authors);
                 every 8th book (indices 7,15,23,…) also gets a 2nd author → ~70 multi-author books.
  Book→Series  : every 5th book (indices 0,5,10,… of 560) is linked to a series → 112 books with
                 series; every 4th of those (indices 0,20,40,…) also links to a second series
                 → ~28 two-series books.
  Book→Genre   : existing single-genre assignment is kept; every 5th book (indices 4,9,14,…)
                 additionally gets a genre from the *next* parent group so that
                 distinct-per-parent counts in test_template.md remain valid.
"""

from library.models import Author, Book, BookSeries, BookSeriesLink, Genre, Language


def create_test_dataset() -> dict:
    """Create the canonical test dataset and return key objects.

    Returns a dict with keys: lang_en, lang_uk, genres (dict), books (list),
    series (list), authors (list).
    """
    lang_en, lang_uk, leaf_genres, genres = _create_languages_and_genres()
    authors = _create_authors()
    books = _create_books(lang_en, lang_uk, leaf_genres)
    series = _create_series()
    _link_books_to_authors(books, authors)
    _link_books_to_series(books, series)
    _add_extra_genres(books, leaf_genres)
    return {
        'lang_en': lang_en,
        'lang_uk': lang_uk,
        'genres': genres,
        'books': books,
        'series': series,
        'authors': authors,
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


def _create_authors() -> list[Author]:
    """Bulk-create 255 authors spread across letter groups A, B, C, Ш, 0-9, and Other.

    Returns:
        List of created Author instances in insertion order.
    """
    def _batch(prefix: str, n: int) -> list[Author]:
        return [Author(last_name=f'{prefix}{i + 1}', first_name='') for i in range(n)]

    return Author.objects.bulk_create(
        # A group
        _batch('Abak', 21) + _batch('Aban', 39) +   # Ab > Aba: 21 + 39 = 60
        _batch('Abi',  42) + _batch('Aby',   8) +   # Ab: +42 +8 = 110
        _batch('Ac',   11) + _batch('Ad',   16) +   # A: +11 +16 = 137
        # B group
        _batch('Ba',   30) + _batch('Be',   28) +   # B: 30 + 28 = 58
        # single-letter groups
        _batch('C',    19) +                         # C: 19
        _batch('Ш',    15) +                         # Ш: 15
        # 0-9 group (digit-prefix last names): 12 authors starting with digits
        [Author(last_name=f'{i}author', first_name='') for i in range(12)] +
        # Other (non-alpha=3, Z=8, Ї=2, Э=1)
        [Author(last_name='!_1', first_name=''),
         Author(last_name='(_2', first_name=''),
         Author(last_name='+_3', first_name='')] +
        _batch('Z', 8) + _batch('Ї', 2) +
        [Author(last_name='Э1', first_name='')]
    )


def _create_books(lang_en: Language, lang_uk: Language, leaf_genres: list[Genre]) -> list[Book]:
    """Bulk-create 560 books (473 English, 87 Ukrainian) across 7 leaf genres.

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
        ('0',    lang_en, [2, 2, 2, 2, 2, 2, 2]),   # 14 digit-prefix (0-9 node)
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

    book_data: list[tuple[str, Language, Genre]] = []
    counters: dict[str, int] = {}

    for prefix, lang, genre_counts in GROUPS:
        for genre, count in zip(leaf_genres, genre_counts):
            for _ in range(count):
                n = counters.get(prefix, 0) + 1
                counters[prefix] = n
                book_data.append((f'{prefix}{n}', lang, genre))

    book_objs = [Book(title=title, language=lang) for title, lang, _ in book_data]
    books = Book.objects.bulk_create(book_objs)

    # Assign primary leaf genres via the auto-created M2M through table
    BookGenre = Book.genres.through
    BookGenre.objects.bulk_create([
        BookGenre(book_id=books[i].pk, genre_id=genre.pk)
        for i, (_, _, genre) in enumerate(book_data)
    ])

    return books


def _create_series() -> list[BookSeries]:
    """Bulk-create 148 book series spread across groups C (54), S (62), T (11), 0-9 (10), and Other (11).

    Returns:
        List of created BookSeries instances in insertion order.
    """
    def _batch(prefix: str, n: int) -> list[BookSeries]:
        return [BookSeries(name=f'{prefix}{i + 1}') for i in range(n)]

    return BookSeries.objects.bulk_create(
        # C group: Ch=36, Cr=18 → 54 (>50 so the C node expands under default min_quantity)
        _batch('Ch', 36) + _batch('Cr', 18) +
        # S group: Sh=6, Sta=28, Ste=26, Sw=2 → 62
        _batch('Sh',  6) + _batch('Sta', 28) + _batch('Ste', 26) + _batch('Sw', 2) +
        # T group: 11
        _batch('T',  11) +
        # 0-9 group (digit-prefix names): 10
        _batch('0series', 10) +
        # Other: non-alpha=4, N=4, В=3 → 11
        [BookSeries(name=f'({i + 1}') for i in range(2)] +
        [BookSeries(name=f'_{i + 1}') for i in range(2)] +
        _batch('N', 4) + _batch('В', 3)
    )


def _link_books_to_authors(books: list[Book], authors: list[Author]) -> None:
    """Assign authors to books using round-robin with some multi-author books.

    Assignment rules:
    - Every book gets exactly 1 author (primary), chosen round-robin over all 255 authors.
    - Every 8th book (index % 8 == 7) additionally gets a 2nd author (next in round-robin).
      This yields ~70 books with 2 authors.

    Args:
        books: All 560 Book instances (ordered as returned by bulk_create).
        authors: All 255 Author instances (ordered as returned by bulk_create).
    """
    BookAuthor = Book.authors.through
    n_authors = len(authors)
    links: list = []

    for i, book in enumerate(books):
        primary = authors[i % n_authors]
        links.append(BookAuthor(book_id=book.pk, author_id=primary.pk))
        if i % 8 == 7:
            secondary = authors[(i + 1) % n_authors]
            links.append(BookAuthor(book_id=book.pk, author_id=secondary.pk))

    BookAuthor.objects.bulk_create(links, ignore_conflicts=True)


def _link_books_to_series(books: list[Book], series: list[BookSeries]) -> None:
    """Link a subset of books to series, with some books belonging to two series.

    Assignment rules:
    - Every 5th book (index % 5 == 0) gets a primary series → 112 books with series.
    - Every 4th of those (i.e. index % 20 == 0) also gets a secondary series → ~28 books
      in 2 series.
    - Sequence numbers are assigned 1-based within each series.

    Args:
        books: All 560 Book instances.
        series: All 108 BookSeries instances.
    """
    n_series = len(series)
    links: list[BookSeriesLink] = []
    series_seq: dict[int, int] = {}  # series pk → next sequence number

    for i, book in enumerate(books):
        if i % 5 != 0:
            continue
        primary_series = series[i // 5 % n_series]
        seq1 = series_seq.get(primary_series.pk, 0) + 1
        series_seq[primary_series.pk] = seq1
        links.append(BookSeriesLink(book_id=book.pk, series_id=primary_series.pk, sequence_number=seq1))

        if i % 20 == 0:
            secondary_series = series[(i // 5 + 1) % n_series]
            seq2 = series_seq.get(secondary_series.pk, 0) + 1
            series_seq[secondary_series.pk] = seq2
            links.append(BookSeriesLink(book_id=book.pk, series_id=secondary_series.pk, sequence_number=seq2))

    BookSeriesLink.objects.bulk_create(links, ignore_conflicts=True)


def _add_extra_genres(books: list[Book], leaf_genres: list[Genre]) -> None:
    """Add a second genre to some books, always from a *different* parent group.

    Assignment rules:
    - Every 5th book (index % 5 == 4) gets an additional genre from the next parent group.
    - leaf_genres order: [dystopia(sf), sci_fi(sf), fantasy(sf), mystery(myst), thriller(myst),
                          adventure(act), nature_animals(act)]
    - Parent-group boundaries: sf=0..2, myst=3..4, act=5..6.
    - For books whose primary genre is in sf (indices 0-2), the extra genre is mystery (index 3).
    - For books in myst (indices 3-4), the extra genre is adventure (index 5).
    - For books in act (indices 5-6), the extra genre is dystopia (index 0).
    - This ensures distinct-per-parent counts from test_template.md remain valid
      (a book counted under sf_fantasy never gets a second sf genre, only a myst or act genre).

    Args:
        books: All 560 Book instances in insertion order.
        leaf_genres: Ordered list [dystopia, sci_fi, fantasy, mystery, thriller, adventure, nature_animals].
    """
    # Mapping: primary genre pk → extra genre to assign
    sf_ids = {leaf_genres[0].pk, leaf_genres[1].pk, leaf_genres[2].pk}
    myst_ids = {leaf_genres[3].pk, leaf_genres[4].pk}
    act_ids = {leaf_genres[5].pk, leaf_genres[6].pk}

    extra_genre_map: dict[int, int] = {}
    for g in leaf_genres[:3]:   # sf → myst
        extra_genre_map[g.pk] = leaf_genres[3].pk
    for g in leaf_genres[3:5]:  # myst → act
        extra_genre_map[g.pk] = leaf_genres[5].pk
    for g in leaf_genres[5:]:   # act → sf
        extra_genre_map[g.pk] = leaf_genres[0].pk

    # Fetch existing primary genre assignment for each candidate book
    BookGenre = Book.genres.through
    candidate_pks = [books[i].pk for i in range(4, len(books), 5)]
    existing = {
        row['book_id']: row['genre_id']
        for row in BookGenre.objects.filter(book_id__in=candidate_pks).values('book_id', 'genre_id')
    }

    extra_links: list = []
    seen: set[tuple[int, int]] = set()
    for book_pk, primary_genre_pk in existing.items():
        extra_pk = extra_genre_map.get(primary_genre_pk)
        if extra_pk and (book_pk, extra_pk) not in seen:
            seen.add((book_pk, extra_pk))
            extra_links.append(BookGenre(book_id=book_pk, genre_id=extra_pk))

    BookGenre.objects.bulk_create(extra_links, ignore_conflicts=True)

    # Suppress unused variable warnings — parent group sets are referenced in comments
    _ = sf_ids, myst_ids, act_ids
