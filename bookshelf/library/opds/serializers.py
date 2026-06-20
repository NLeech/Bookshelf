"""
OPDS serializers — pure Python functions that convert model objects or static
data into neutral feed dicts consumed by OPDSRenderer.

No XML knowledge lives here.  No DRF serializer classes are used.
"""
from collections.abc import Iterable
from datetime import datetime
from typing import NotRequired, TypedDict
from urllib.parse import quote

from django.urls import reverse
from django.utils.timezone import now
from rest_framework.request import Request

from library.models import Author, Book, BookSeries
from library.services import AlphabetTree, get_content_type


# MIME type constants shared with renderers and views.
NAV_TYPE = 'application/atom+xml;profile=opds-catalog;kind=navigation'
ACQ_TYPE = 'application/atom+xml;profile=opds-catalog;kind=acquisition'
OPENSEARCH_TYPE = 'application/opensearchdescription+xml'
ATOM_TYPE = 'application/atom+xml'

# Type advertised by the mandatory ``rel="alternate"`` link on thin book
# entries — it points at the complete catalog entry.
ALTERNATE_ENTRY_TYPE = 'application/atom+xml;type=entry;profile=opds-catalog'

# Static placeholder/branding assets (paths are URL-encoded for the feed).
LOGO_PATH = '/static/img/Logo 64x64x8.png'
NO_COVER_FULL_PATH = '/static/img/no_cover 600x900.jpeg'
NO_COVER_THUMBNAIL_PATH = '/static/img/no_cover 40x60.jpeg'

# Query params that are catalog-wide "sticky" preferences: when present
# on a request they are re-appended to every link that targets another
# browsable feed, so the preference survives link-following.  Add a new sticky
# preference here
STICKY_QUERY_PARAMS = ('detail',)

def _opds_base(request: Request) -> str:
    """Return the absolute OPDS catalog base URL (the ``opds:root`` path).

    The base path is derived from the URLconf via ``reverse('opds:root')`` —
    the URLconf is the single source of truth, so the catalog can be remounted
    (or re-versioned) without touching this module.

    Args:
        request: The current HTTP request.

    Returns:
        The absolute base URL all feed links are built from.
    """
    return request.build_absolute_uri(reverse('opds:root'))


# ---------------------------------------------------------------------------
# Feed dict contract — the neutral structures consumed by OPDSRenderer.
# ---------------------------------------------------------------------------

class LinkDict(TypedDict):
    """A single Atom ``<link>`` element."""

    rel: str
    href: str
    type: str
    title: str | None


class AuthorRefDict(TypedDict):
    """An Atom ``<author>`` element (book/acquisition entries only)."""

    name: str
    uri: NotRequired[str]


class CalibreSeriesDict(TypedDict):
    """A ``<calibre:series>``/``<calibre:series_index>`` pair."""

    name: str
    index: int


class EntryDict(TypedDict):
    """A single Atom ``<entry>`` within a feed."""

    id: str
    title: str
    updated: datetime | None
    content: str | None
    summary: str | None
    authors: list[AuthorRefDict]
    links: list[LinkDict]
    calibre_series: NotRequired[list[CalibreSeriesDict]]
    content_type: NotRequired[str]


# Pagination link block: 'first'/'next'/'previous' → URL or None.
PaginationDict = dict[str, str | None]


class FeedDict(TypedDict):
    """A complete OPDS feed ready for rendering."""

    id: str
    title: str
    updated: datetime
    kind: str
    self_link: str
    start_link: str
    pagination: PaginationDict | None
    entries: list[EntryDict]


def wants_thick_entries(request: Request) -> bool:
    """Whether the client requested complete (thick) book entries (having full metadata, see docs/TDD_OPDS.md §6.5a ).

    Args:
        request: The current HTTP request.

    Returns:
        True when ``?detail=thick`` is present on the request.
    """
    return request.query_params.get('detail') == 'thick'


def _with_sticky_params(href: str, request: Request) -> str:
    """Re-append the request's sticky catalog-wide params to a feed link.

    Every sticky param
    (see :data:`STICKY_QUERY_PARAMS`) present on the current request is appended
    to ``href`` so the preference survives link-following through navigation,
    search, and drill-down.  Params already present in ``href`` (e.g. on a self
    link built from ``request.build_absolute_uri()``) are not duplicated, and
    any existing query string is preserved verbatim — so template links such as
    ``…/search/?q={searchTerms}`` keep their placeholder intact.

    Args:
        href: The absolute link URL to (possibly) annotate.
        request: The current HTTP request (source of the sticky params).

    Returns:
        The href, with the active sticky params appended when missing.
    """
    extra: list[str] = []
    for key in STICKY_QUERY_PARAMS:
        value = request.query_params.get(key)
        if value is None:
            continue
        token = f'{key}={quote(value, safe="")}'
        if token in href:
            continue
        extra.append(token)
    if not extra:
        return href
    separator = '&' if '?' in href else '?'
    return f'{href}{separator}{"&".join(extra)}'


def _logo_thumbnail_link(request: Request) -> LinkDict:
    """Return the application-logo thumbnail link for a non-book entry.

    Args:
        request: The current HTTP request (used to build the absolute URI).

    Returns:
        A link dict for ``rel="http://opds-spec.org/image/thumbnail"``.
    """
    return {
        'rel': 'http://opds-spec.org/image/thumbnail',
        'href': request.build_absolute_uri(quote(LOGO_PATH)),
        'type': 'image/png',
        'title': None,
    }


def _book_thumbnail_url(book: Book, request: Request) -> str:
    """Return the absolute cover-thumbnail URL for a book.

    Uses the OPDS-specific 40x60 thumbnail when the book has a cover, falling
    back to the ``no_cover 40x60.jpeg`` placeholder otherwise.
    """
    if book.cover:
        return request.build_absolute_uri(book.cover_opds_thumbnail.url)
    return request.build_absolute_uri(quote(NO_COVER_THUMBNAIL_PATH))


def _book_cover_url(book: Book, request: Request) -> str:
    """Return the absolute full-size cover URL for a book.

    Falls back to the ``no_cover 600x900.jpeg`` placeholder when the book has
    no cover.
    """
    if book.cover:
        return request.build_absolute_uri(book.cover.url)
    return request.build_absolute_uri(quote(NO_COVER_FULL_PATH))


def build_root_feed(request: Request) -> FeedDict:
    """Build the root OPDS navigation feed dict.

    Returns a fixed set of entries.

    Args:
        request: The current HTTP request (used to build absolute URIs).

    Returns:
        A feed dict conforming to the feed dict contract.
    """
    opds_base = _opds_base(request)
    self_link = _with_sticky_params(opds_base, request)

    feed_updated = now()

    entries: list[EntryDict] = [
        {
            'id': 'tag:bookshelf:authors',
            'title': 'Authors',
            'updated': feed_updated,
            'content': 'Browse by author',
            'summary': None,
            'authors': [],
            'links': [
                {
                    'rel': 'subsection',
                    'href': _with_sticky_params(opds_base + 'authors/tree/', request),
                    'type': NAV_TYPE,
                    'title': None,
                },
            ],
        },
        {
            'id': 'tag:bookshelf:genres',
            'title': 'Genres',
            'updated': feed_updated,
            'content': 'Browse by genre',
            'summary': None,
            'authors': [],
            'links': [
                {
                    'rel': 'subsection',
                    'href': _with_sticky_params(opds_base + 'genres/', request),
                    'type': NAV_TYPE,
                    'title': None,
                },
            ],
        },
        {
            'id': 'tag:bookshelf:series',
            'title': 'Series',
            'updated': feed_updated,
            'content': 'Browse by series',
            'summary': None,
            'authors': [],
            'links': [
                {
                    'rel': 'subsection',
                    'href': _with_sticky_params(opds_base + 'series/tree/', request),
                    'type': NAV_TYPE,
                    'title': None,
                },
            ],
        },
        {
            'id': 'tag:bookshelf:books',
            'title': 'Books',
            'updated': feed_updated,
            'content': 'Browse by title',
            'summary': None,
            'authors': [],
            'links': [
                {
                    'rel': 'subsection',
                    'href': _with_sticky_params(opds_base + 'books/tree/', request),
                    'type': NAV_TYPE,
                    'title': None,
                },
            ],
        },
        {
            'id': 'tag:bookshelf:search',
            'title': 'Search',
            'updated': feed_updated,
            'content': 'Search the catalog',
            'summary': None,
            'authors': [],
            'links': [
                {
                    'rel': 'search',
                    'href': opds_base + 'search/description.xml',
                    'type': OPENSEARCH_TYPE,
                    'title': None,
                },
                {
                    'rel': 'search',
                    'href': _with_sticky_params(opds_base + 'search/?q={searchTerms}', request),
                    'type': ATOM_TYPE,
                    'title': None,
                },
            ],
        },
    ]

    for entry in entries:
        entry['links'].append(_logo_thumbnail_link(request))

    return {
        'id': 'tag:bookshelf:root',
        'title': 'Bookshelf Catalog',
        'updated': feed_updated,
        'icon': request.build_absolute_uri(quote(LOGO_PATH)),
        'kind': 'navigation',
        'self_link': self_link,
        'start_link': self_link,
        'pagination': None,
        'entries': entries,
    }


# ---------------------------------------------------------------------------
# Author serializers
# ---------------------------------------------------------------------------

def _url_encode_regex(regex: str) -> str:
    """URL-encode a regex string for use in a query parameter."""
    return quote(regex, safe='')


def _build_author_tree_child_href(child: AlphabetTree, opds_base: str) -> str:
    """Return the link href for an author tree child entry.

    Expandable nodes (have children) link to the sub-tree URL.
    Leaf nodes with a filter link to the flat results with ?filter=.
    Leaf nodes with only a regex link to the flat results with ?regex= (URL-encoded).

    Args:
        child: An AlphabetTree node.
        opds_base: Absolute OPDS catalog base URL (see :func:`_opds_base`).

    Returns:
        The href string for this child's navigation link.
    """
    if child.entries:
        return opds_base + f'authors/tree/{child.name}/'
    elif child.filter:
        return opds_base + f'authors/?filter={child.filter}'
    else:
        return opds_base + f'authors/?regex={_url_encode_regex(child.regex)}'


def build_author_tree_feed(node: AlphabetTree, request: Request) -> FeedDict:
    """Build a navigation alphabet-tree feed for authors.

    When ``node.name`` is ``''`` (the root AlphabetTree), renders its direct
    children with no synthetic "all" entry.  When ``node.name`` is non-empty
    (a named sub-tree node such as ``'a'`` or ``'other'``), prepends a
    synthetic ``"all <name>"`` entry as the first child.

    Args:
        node: An AlphabetTree node — either the root or a named expandable node.
        request: The current HTTP request.

    Returns:
        A feed dict conforming to the feed dict contract.
    """
    opds_base = _opds_base(request)
    start_link = _with_sticky_params(opds_base, request)

    if not node.name:
        feed_id = 'tag:bookshelf:authors'
        feed_title = 'Authors'
        self_link = _with_sticky_params(opds_base + 'authors/tree/', request)
    else:
        feed_id = f'tag:bookshelf:authors:tree:{node.name}'
        feed_title = f'Authors — {str(node)}'
        self_link = _with_sticky_params(opds_base + f'authors/tree/{node.name}/', request)

    entries: list[EntryDict] = []

    # For sub-tree nodes (not root), prepend synthetic "all <prefix>" entry.
    if node.name:
        all_title = f'all {node}'
        if node.filter:
            all_href = opds_base + f'authors/?filter={node.filter}'
        else:
            all_href = opds_base + f'authors/?regex={_url_encode_regex(node.regex)}'
        all_href = _with_sticky_params(all_href, request)

        entries.append({
            'id': f'tag:bookshelf:authors:tree:{node.name}:all',
            'title': all_title,
            'updated': None,
            'content': str(node.quantity),
            'summary': None,
            'authors': [],
            'links': [
                {
                    'rel': 'subsection',
                    'href': all_href,
                    'type': NAV_TYPE,
                    'title': None,
                }
            ],
        })

    # Render child entries.
    for child in node.entries:
        href = _with_sticky_params(_build_author_tree_child_href(child, opds_base), request)
        entries.append({
            'id': f'tag:bookshelf:authors:tree:{child.name}',
            'title': str(child),
            'updated': None,
            'content': str(child.quantity),
            'summary': None,
            'authors': [],
            'links': [
                {
                    'rel': 'subsection',
                    'href': href,
                    'type': NAV_TYPE,
                    'title': None,
                }
            ],
        })

    for entry in entries:
        entry['links'].append(_logo_thumbnail_link(request))

    return {
        'id': feed_id,
        'title': feed_title,
        'updated': now(),
        'kind': 'navigation',
        'self_link': self_link,
        'start_link': start_link,
        'pagination': None,
        'entries': entries,
    }


def build_author_results_feed(
    authors_page: list[Author],
    pagination: PaginationDict | None,
    request: Request,
) -> FeedDict:
    """Build a flat, paginated navigation feed of authors.

    Each entry links to the author's detail feed at
    ``opds:root/authors/<pk>/``.

    Args:
        authors_page: A list of Author instances for the current page.
        pagination: Pagination dict with 'first', 'next', 'previous' keys
            (values are URLs or None), or None when there is no pagination.
        request: The current HTTP request.

    Returns:
        A feed dict conforming to the feed dict contract.
    """
    opds_base = _opds_base(request)
    self_link = _with_sticky_params(request.build_absolute_uri(), request)
    start_link = _with_sticky_params(opds_base, request)

    entries: list[EntryDict] = [
        {
            'id': f'tag:bookshelf:author:{author.pk}',
            'title': author.full_name,
            'updated': author.updated_at,
            'content': f'{getattr(author, "book_count", 0)} books',
            'summary': None,
            'authors': [],
            'links': [
                {
                    'rel': 'subsection',
                    'href': _with_sticky_params(opds_base + f'authors/{author.pk}/', request),
                    'type': NAV_TYPE,
                    'title': None,
                },
                _logo_thumbnail_link(request),
            ],
        }
        for author in authors_page
    ]

    return {
        'id': 'tag:bookshelf:authors',
        'title': 'Authors',
        'updated': now(),
        'kind': 'navigation',
        'self_link': self_link,
        'start_link': start_link,
        'pagination': pagination,
        'entries': entries,
    }


def build_author_detail_feed(author: Author, request: Request) -> FeedDict:
    """Build the author detail navigation feed.

    Returns exactly three sub-feed navigation entries:
    - Books by Title → acquisition
    - New Arrivals → acquisition
    - Books by Series → navigation

    Args:
        author: An Author model instance.
        request: The current HTTP request.

    Returns:
        A feed dict conforming to the feed dict contract.
    """
    opds_base = _opds_base(request)
    self_link = _with_sticky_params(opds_base + f'authors/{author.pk}/', request)
    start_link = _with_sticky_params(opds_base, request)

    entries: list[EntryDict] = [
        {
            'id': f'tag:bookshelf:author:{author.pk}:books',
            'title': 'Books by Title',
            'updated': author.updated_at,
            'content': 'All books by this author, sorted alphabetically',
            'summary': None,
            'authors': [],
            'links': [
                {
                    'rel': 'subsection',
                    'href': _with_sticky_params(opds_base + f'authors/{author.pk}/books/', request),
                    'type': ACQ_TYPE,
                    'title': None,
                },
                _logo_thumbnail_link(request),
            ],
        },
        {
            'id': f'tag:bookshelf:author:{author.pk}:books:recent',
            'title': 'New Arrivals',
            'updated': author.updated_at,
            'content': 'Recently added books by this author',
            'summary': None,
            'authors': [],
            'links': [
                {
                    'rel': 'subsection',
                    'href': _with_sticky_params(opds_base + f'authors/{author.pk}/books/recent/', request),
                    'type': ACQ_TYPE,
                    'title': None,
                },
                _logo_thumbnail_link(request),
            ],
        },
        {
            'id': f'tag:bookshelf:author:{author.pk}:series',
            'title': 'Books by Series',
            'updated': author.updated_at,
            'content': "Browse this author's books by series",
            'summary': None,
            'authors': [],
            'links': [
                {
                    'rel': 'subsection',
                    'href': _with_sticky_params(opds_base + f'authors/{author.pk}/series/', request),
                    'type': NAV_TYPE,
                    'title': None,
                },
                _logo_thumbnail_link(request),
            ],
        },
    ]

    return {
        'id': f'tag:bookshelf:author:{author.pk}',
        'title': author.full_name,
        'updated': author.updated_at,
        'kind': 'navigation',
        'self_link': self_link,
        'start_link': start_link,
        'pagination': None,
        'entries': entries,
    }


def build_author_series_feed(
    author: Author,
    request: Request,
    series_with_counts: Iterable[BookSeries],
    standalone_count: int = 0,
) -> FeedDict:
    """Build the author series navigation feed.

    When ``standalone_count > 0``, prepends a "Standalone Books" entry as
    the first entry linking to ``opds:root/authors/<pk>/books/?series=none``.
    Followed by one navigation entry per series, linking to
    ``opds:root/series/<pk>/``.

    Args:
        author: An Author model instance.
        request: The current HTTP request.
        series_with_counts: A queryset of BookSeries annotated with
            ``author_book_count`` (distinct books by this author in that series).
        standalone_count: Number of the author's books not linked to any series.

    Returns:
        A feed dict conforming to the feed dict contract.
    """
    opds_base = _opds_base(request)
    self_link = _with_sticky_params(opds_base + f'authors/{author.pk}/series/', request)
    start_link = _with_sticky_params(opds_base, request)

    entries: list[EntryDict] = []

    if standalone_count > 0:
        entries.append({
            'id': f'tag:bookshelf:author:{author.pk}:standalone',
            'title': 'Standalone Books',
            'updated': author.updated_at,
            'content': f'{standalone_count} standalone book(s)',
            'summary': None,
            'authors': [],
            'links': [
                {
                    'rel': 'subsection',
                    'href': _with_sticky_params(opds_base + f'authors/{author.pk}/books/?series=none', request),
                    'type': ACQ_TYPE,
                    'title': None,
                },
                _logo_thumbnail_link(request),
            ],
        })

    for series in series_with_counts:
        count = getattr(series, 'author_book_count', 0)
        entries.append({
            'id': f'tag:bookshelf:series:{series.pk}',
            'title': series.name,
            'updated': series.updated_at,
            'content': f'{count} book(s) in this series',
            'summary': None,
            'authors': [],
            'links': [
                {
                    'rel': 'subsection',
                    'href': _with_sticky_params(opds_base + f'series/{series.pk}/', request),
                    'type': NAV_TYPE,
                    'title': None,
                },
                _logo_thumbnail_link(request),
            ],
        })

    return {
        'id': f'tag:bookshelf:author:{author.pk}:series',
        'title': f'{author.full_name} — Series',
        'updated': author.updated_at,
        'kind': 'navigation',
        'self_link': self_link,
        'start_link': start_link,
        'pagination': None,
        'entries': entries,
    }


def _build_book_entry(
    book: Book,
    request: Request,
    opds_base: str,
    thick: bool,
    include_alternate: bool = True,
) -> EntryDict:
    """Build a single OPDS book (acquisition) entry dict.

    Implements the thin/thick split.  Every entry carries the
    acquisition link and the cover thumbnail.  Listing entries also carry the
    mandatory ``rel="alternate"`` link to the complete entry at
    ``opds_base/books/<pk>/``; the standalone book-detail feed (which *is* the
    alternate target) omits it via ``include_alternate=False``.  Thick entries
    additionally carry the complete book shape: the sanitized description as
    ``<content type="xhtml">``, ``<calibre:series>`` metadata, the full-size
    cover image, and author/series ``rel="related"`` links.  No Atom
    ``<author>`` element is ever emitted — authors are represented solely by
    ``rel="related"`` links on thick entries.

    Args:
        book: A Book model instance.
        request: The current HTTP request.
        opds_base: Absolute base URL ending.
        thick: When True, render the complete entry; otherwise render thin.
        include_alternate: When True, emit the ``rel="alternate"`` link to the
            complete entry.  Set False for the book-detail feed itself.

    Returns:
        An entry dict conforming to the feed dict contract.
    """
    links: list[LinkDict] = [
        {
            'rel': 'http://opds-spec.org/acquisition',
            'href': opds_base + f'books/{book.pk}/download/',
            'type': get_content_type(book.file_type),
            'title': None,
        },
    ]

    if include_alternate:
        links.append({
            'rel': 'alternate',
            'href': opds_base + f'books/{book.pk}/',
            'type': ALTERNATE_ENTRY_TYPE,
            'title': None,
        })

    links.append({
        'rel': 'http://opds-spec.org/image/thumbnail',
        'href': _book_thumbnail_url(book, request),
        'type': 'image/jpeg',
        'title': None,
    })

    entry: EntryDict = {
        'id': f'tag:bookshelf:book:{book.pk}',
        'title': book.title,
        'updated': book.updated_at,
        'content': None,
        'summary': None,
        'authors': [],
        'links': links,
    }

    if not thick:
        return entry

    # Full-size cover image (thick only).
    links.append({
        'rel': 'http://opds-spec.org/image',
        'href': _book_cover_url(book, request),
        'type': 'image/jpeg',
        'title': None,
    })

    # Author related-links — the only representation of authors on a book entry.
    for author in book.authors.all():
        links.append({
            'rel': 'related',
            'href': _with_sticky_params(opds_base + f'authors/{author.pk}/', request),
            'type': NAV_TYPE,
            'title': author.full_name,
        })

    # Series: structured <calibre:*> pair + a tappable rel="related" link.
    calibre_series: list[CalibreSeriesDict] = []
    for series_link in book.bookserieslink_set.select_related('series').all():
        series = series_link.series
        calibre_series.append({
            'name': series.name.strip(),
            'index': series_link.sequence_number,
        })
        links.append({
            'rel': 'related',
            'href': _with_sticky_params(opds_base + f'series/{series.pk}/', request),
            'type': NAV_TYPE,
            'title': series.name.strip(),
        })

    if calibre_series:
        entry['calibre_series'] = calibre_series

    if book.description:
        entry['content'] = book.description
        entry['content_type'] = 'xhtml'

    return entry


def _build_book_tree_child_href(
    child: AlphabetTree, opds_base: str, base_url: str,
) -> str:
    """Return the link href for a book tree child entry.

    Expandable nodes (have children) link to the sub-tree URL.
    Leaf nodes with a filter link to the flat results with ?filter=.
    Leaf nodes with only a regex link to the flat results with ?regex= (URL-encoded).

    Args:
        child: An AlphabetTree node.
        opds_base: Absolute OPDS catalog base URL (see :func:`_opds_base`).
        base_url: The path prefix for this tree (``'books'`` for the main book
            tree, ``'genres/<pk>/books'`` for the genre-scoped tree).

    Returns:
        The href string for this child's navigation link.
    """
    if child.entries:
        return opds_base + f'{base_url}/tree/{child.name}/'
    elif child.filter:
        return opds_base + f'{base_url}/?filter={child.filter}'
    else:
        return opds_base + f'{base_url}/?regex={_url_encode_regex(child.regex)}'


def build_book_tree_feed(
    node: AlphabetTree, request: Request, base_url: str = 'books',
) -> FeedDict:
    """Build a navigation alphabet-tree feed for books.

    When ``node.name`` is ``''`` (the root AlphabetTree), renders its direct
    children with no synthetic "all" entry.  When ``node.name`` is non-empty
    (a named sub-tree node such as ``'a'`` or ``'other'``), prepends a
    synthetic ``"all <name>"`` entry as the first child.

    Args:
        node: An AlphabetTree node — either the root or a named expandable node.
        request: The current HTTP request.
        base_url: The path prefix for this tree (``'books'`` for the main book
            tree, ``'genres/<pk>/books'`` for the genre-scoped tree).  The same
            builder serves both.

    Returns:
        A feed dict conforming to the feed dict contract.
    """
    opds_base = _opds_base(request)
    start_link = _with_sticky_params(opds_base, request)

    id_base = f'tag:bookshelf:{base_url.replace("/", ":")}'

    if not node.name:
        feed_id = id_base
        feed_title = 'Books'
        self_link = _with_sticky_params(opds_base + f'{base_url}/tree/', request)
    else:
        feed_id = f'{id_base}:tree:{node.name}'
        feed_title = f'Books — {str(node)}'
        self_link = _with_sticky_params(
            opds_base + f'{base_url}/tree/{node.name}/', request
        )

    entries: list[EntryDict] = []

    # For sub-tree nodes (not root), prepend synthetic "all <prefix>" entry.
    if node.name:
        all_title = f'all {node}'
        if node.filter:
            all_href = opds_base + f'{base_url}/?filter={node.filter}'
        else:
            all_href = opds_base + f'{base_url}/?regex={_url_encode_regex(node.regex)}'
        all_href = _with_sticky_params(all_href, request)

        entries.append({
            'id': f'{id_base}:tree:{node.name}:all',
            'title': all_title,
            'updated': None,
            'content': str(node.quantity),
            'summary': None,
            'authors': [],
            'links': [
                {
                    'rel': 'subsection',
                    'href': all_href,
                    'type': NAV_TYPE,
                    'title': None,
                }
            ],
        })

    # Render child entries.
    for child in node.entries:
        href = _with_sticky_params(
            _build_book_tree_child_href(child, opds_base, base_url), request
        )
        entries.append({
            'id': f'{id_base}:tree:{child.name}',
            'title': str(child),
            'updated': None,
            'content': str(child.quantity),
            'summary': None,
            'authors': [],
            'links': [
                {
                    'rel': 'subsection',
                    'href': href,
                    'type': NAV_TYPE,
                    'title': None,
                }
            ],
        })

    for entry in entries:
        entry['links'].append(_logo_thumbnail_link(request))

    return {
        'id': feed_id,
        'title': feed_title,
        'updated': now(),
        'kind': 'navigation',
        'self_link': self_link,
        'start_link': start_link,
        'pagination': None,
        'entries': entries,
    }


def build_book_results_feed(
    books_page: list[Book],
    pagination: PaginationDict | None,
    request: Request,
    feed_id: str = 'tag:bookshelf:books',
    feed_title: str = 'Books',
    thick: bool = False,
) -> FeedDict:
    """Build a paginated acquisition feed of books.

    This is the single builder for every flat book listing in the catalog —
    the top-level ``opds:root/books/`` results (with optional
    ``?filter=``/``?regex=``) as well as the author-, series-, and
    genre-scoped book lists.  Scoped callers pass ``feed_id``/``feed_title`` to
    label their feed; the defaults cover the top-level books endpoint.

    Book entries are thin by default; ``thick=True`` (driven by
    ``?detail=thick``) renders the complete book shape inline.  Per the
    catalog-is-fully-browsable convention every entry carries the acquisition
    link; download permission is enforced at the download endpoint.

    Args:
        books_page: A list of Book instances for the current page.
        pagination: Pagination dict with 'first', 'next', 'previous' keys
            (values are URLs or None), or None when there is no pagination.
        request: The current HTTP request.
        feed_id: The feed ``<id>`` tag URI (defaults to the top-level books id).
        feed_title: The feed title (defaults to ``'Books'``).
        thick: Render complete (thick) entries when True.

    Returns:
        A feed dict conforming to the feed dict contract.
    """
    opds_base = _opds_base(request)
    self_link = _with_sticky_params(request.build_absolute_uri(), request)
    start_link = _with_sticky_params(opds_base, request)

    entries: list[EntryDict] = [
        _build_book_entry(book, request, opds_base, thick)
        for book in books_page
    ]

    return {
        'id': feed_id,
        'title': feed_title,
        'updated': now(),
        'kind': 'acquisition',
        'self_link': self_link,
        'start_link': start_link,
        'pagination': pagination,
        'entries': entries,
    }


def build_book_detail_feed(book: Book, request: Request) -> FeedDict:
    """Build the standalone book-detail acquisition feed.

    The feed holds a single **complete** book entry — the same shape as a thick
    listing entry, minus the ``rel="alternate"`` link (this feed *is* the
    alternate target).  Per the catalog-is-fully-browsable convention the
    acquisition link is always rendered; download permission is enforced at the
    download endpoint, not in the feed.

    Args:
        book: A Book model instance (authors / series prefetched by the view).
        request: The current HTTP request.

    Returns:
        A feed dict conforming to the feed dict contract, with one entry.
    """
    opds_base = _opds_base(request)
    self_link = _with_sticky_params(opds_base + f'books/{book.pk}/', request)
    start_link = _with_sticky_params(opds_base, request)

    entry = _build_book_entry(
        book, request, opds_base, thick=True, include_alternate=False,
    )

    return {
        'id': f'tag:bookshelf:book:{book.pk}',
        'title': book.title,
        'updated': book.updated_at,
        'kind': 'acquisition',
        'self_link': self_link,
        'start_link': start_link,
        'pagination': None,
        'entries': [entry],
    }
