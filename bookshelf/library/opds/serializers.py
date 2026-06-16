"""
OPDS serializers — pure Python functions that convert model objects or static
data into neutral feed dicts consumed by OPDSRenderer.

No XML knowledge lives here.  No DRF serializer classes are used.
"""
from urllib.parse import quote

from django.urls import reverse
from django.utils.timezone import now


# MIME type constants shared with renderers and views.
NAV_TYPE = 'application/atom+xml;profile=opds-catalog;kind=navigation'
ACQ_TYPE = 'application/atom+xml;profile=opds-catalog;kind=acquisition'
OPENSEARCH_TYPE = 'application/opensearchdescription+xml'
ATOM_TYPE = 'application/atom+xml'


def build_root_feed(request) -> dict:
    """Build the root OPDS navigation feed dict.

    Returns a fixed set of five entries:
    Authors, Genres, Series, Books, Search.

    Args:
        request: The current HTTP request (used to build absolute URIs).

    Returns:
        A feed dict conforming to the feed dict contract.
    """
    self_link = request.build_absolute_uri(reverse('opds:root'))
    opds_base = request.build_absolute_uri('/opds/v1/')

    feed_updated = now()

    entries = [
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
                    'href': opds_base + 'authors/tree/',
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
                    'href': opds_base + 'genres/',
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
                    'href': opds_base + 'series/tree/',
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
                    'href': opds_base + 'books/tree/',
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
                    'href': opds_base + 'search/?q={searchTerms}',
                    'type': ATOM_TYPE,
                    'title': None,
                },
            ],
        },
    ]

    return {
        'id': 'tag:bookshelf:root',
        'title': 'Bookshelf Catalog',
        'updated': feed_updated,
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


def _build_author_tree_child_href(child, opds_base: str) -> str:
    """Return the link href for an author tree child entry.

    Expandable nodes (have children) link to the sub-tree URL.
    Leaf nodes with a filter link to the flat results with ?filter=.
    Leaf nodes with only a regex link to the flat results with ?regex= (URL-encoded).

    Args:
        child: An AlphabetTree node.
        opds_base: Absolute base URL ending in '/opds/v1/'.

    Returns:
        The href string for this child's navigation link.
    """
    if child.entries:
        return opds_base + f'authors/tree/{child.name}/'
    elif child.filter:
        return opds_base + f'authors/?filter={child.filter}'
    else:
        return opds_base + f'authors/?regex={_url_encode_regex(child.regex)}'


def build_author_tree_feed(node, request) -> dict:
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
    opds_base = request.build_absolute_uri('/opds/v1/')
    start_link = request.build_absolute_uri('/opds/v1/')

    if not node.name:
        feed_id = 'tag:bookshelf:authors'
        feed_title = 'Authors'
        self_link = opds_base + 'authors/tree/'
    else:
        feed_id = f'tag:bookshelf:authors:tree:{node.name}'
        feed_title = f'Authors — {str(node)}'
        self_link = opds_base + f'authors/tree/{node.name}/'

    entries = []

    # For sub-tree nodes (not root), prepend synthetic "all <prefix>" entry.
    if node.name:
        all_title = 'all Other' if node.name == 'other' else f'all {node.name}'
        if node.filter:
            all_href = opds_base + f'authors/?filter={node.filter}'
        else:
            all_href = opds_base + f'authors/?regex={_url_encode_regex(node.regex)}'

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
        href = _build_author_tree_child_href(child, opds_base)
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


def build_author_results_feed(authors_page, pagination, request) -> dict:
    """Build a flat, paginated navigation feed of authors.

    Each entry links to the author's detail feed at
    ``/opds/v1/authors/<pk>/``.

    Args:
        authors_page: A list of Author instances for the current page.
        pagination: Pagination dict with 'first', 'next', 'previous' keys
            (values are URLs or None), or None when there is no pagination.
        request: The current HTTP request.

    Returns:
        A feed dict conforming to the feed dict contract.
    """
    opds_base = request.build_absolute_uri('/opds/v1/')
    self_link = request.build_absolute_uri()
    start_link = request.build_absolute_uri('/opds/v1/')

    entries = [
        {
            'id': f'tag:bookshelf:author:{author.pk}',
            'title': author.full_name,
            'updated': author.updated_at,
            'content': None,
            'summary': None,
            'authors': [],
            'links': [
                {
                    'rel': 'subsection',
                    'href': opds_base + f'authors/{author.pk}/',
                    'type': NAV_TYPE,
                    'title': None,
                }
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


def build_author_detail_feed(author, request) -> dict:
    """Build the author detail navigation feed.

    Returns exactly three sub-feed navigation entries:
    - All Books (A–Z) → acquisition
    - Recently Added → acquisition
    - Books by Series → navigation

    Args:
        author: An Author model instance.
        request: The current HTTP request.

    Returns:
        A feed dict conforming to the feed dict contract.
    """
    opds_base = request.build_absolute_uri('/opds/v1/')
    self_link = opds_base + f'authors/{author.pk}/'
    start_link = request.build_absolute_uri('/opds/v1/')

    entries = [
        {
            'id': f'tag:bookshelf:author:{author.pk}:books',
            'title': 'All Books (A–Z)',
            'updated': author.updated_at,
            'content': 'All books by this author, sorted alphabetically',
            'summary': None,
            'authors': [],
            'links': [
                {
                    'rel': 'subsection',
                    'href': opds_base + f'authors/{author.pk}/books/',
                    'type': ACQ_TYPE,
                    'title': None,
                }
            ],
        },
        {
            'id': f'tag:bookshelf:author:{author.pk}:books:recent',
            'title': 'Recently Added',
            'updated': author.updated_at,
            'content': 'Recently added books by this author',
            'summary': None,
            'authors': [],
            'links': [
                {
                    'rel': 'subsection',
                    'href': opds_base + f'authors/{author.pk}/books/recent/',
                    'type': ACQ_TYPE,
                    'title': None,
                }
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
                    'href': opds_base + f'authors/{author.pk}/series/',
                    'type': NAV_TYPE,
                    'title': None,
                }
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


def build_author_series_feed(author, request, series_with_counts, standalone_count: int = 0) -> dict:
    """Build the author series navigation feed.

    When ``standalone_count > 0``, prepends a "Standalone Books" entry as
    the first entry linking to ``/opds/v1/authors/<pk>/books/?series=none``.
    Followed by one navigation entry per series, linking to
    ``/opds/v1/series/<pk>/``.

    Args:
        author: An Author model instance.
        request: The current HTTP request.
        series_with_counts: A queryset of BookSeries annotated with
            ``author_book_count`` (distinct books by this author in that series).
        standalone_count: Number of the author's books not linked to any series.

    Returns:
        A feed dict conforming to the feed dict contract.
    """
    opds_base = request.build_absolute_uri('/opds/v1/')
    self_link = opds_base + f'authors/{author.pk}/series/'
    start_link = request.build_absolute_uri('/opds/v1/')

    entries = []

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
                    'href': opds_base + f'authors/{author.pk}/books/?series=none',
                    'type': ACQ_TYPE,
                    'title': None,
                }
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
                    'href': opds_base + f'series/{series.pk}/',
                    'type': NAV_TYPE,
                    'title': None,
                }
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


def build_author_books_feed(
    books_page,
    pagination,
    author,
    request,
    feed_id: str | None = None,
    feed_title: str | None = None,
) -> dict:
    """Build a paginated acquisition feed of an author's books.

    Used by both ``AuthorBooksFeedView`` (A–Z) and
    ``AuthorRecentBooksFeedView`` (recently added).  Callers may override
    ``feed_id`` and ``feed_title`` to distinguish the two feeds.

    Each book entry always includes an acquisition link pointing to the
    book's download endpoint.  The catalog is fully browsable; download
    permission is enforced at the download endpoint itself.

    Args:
        books_page: A list of Book instances for the current page.
        pagination: Pagination dict or None.
        author: The Author model instance.
        request: The current HTTP request.
        feed_id: Override the default feed ``<id>`` tag URI.
        feed_title: Override the default feed title.

    Returns:
        A feed dict conforming to the feed dict contract.
    """
    opds_base = request.build_absolute_uri('/opds/v1/')
    self_link = request.build_absolute_uri()
    start_link = request.build_absolute_uri('/opds/v1/')

    if feed_id is None:
        feed_id = f'tag:bookshelf:author:{author.pk}:books'
    if feed_title is None:
        feed_title = f'{author.full_name} — Books'

    entries = []
    for book in books_page:
        links = [{
            'rel': 'http://opds-spec.org/acquisition',
            'href': opds_base + f'books/{book.pk}/download/',
            'type': 'application/octet-stream',
            'title': None,
        }]

        entries.append({
            'id': f'tag:bookshelf:book:{book.pk}',
            'title': book.title,
            'updated': book.updated_at,
            'content': None,
            'summary': book.description[:1000] if book.description else None,
            'authors': [
                {
                    'name': a.full_name,
                    'uri': opds_base + f'authors/{a.pk}/',
                }
                for a in book.authors.all()
            ],
            'links': links,
        })

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
