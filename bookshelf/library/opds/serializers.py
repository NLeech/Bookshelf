"""
OPDS serializers — pure Python functions that convert model objects or static
data into neutral feed dicts consumed by OPDSRenderer.

No XML knowledge lives here.  No DRF serializer classes are used.
"""
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
