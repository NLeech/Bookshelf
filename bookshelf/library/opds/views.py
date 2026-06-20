from django.conf import settings
from django.db.models import Count, Exists, OuterRef, Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.utils.urls import remove_query_param
from rest_framework.views import APIView

from library.models import Author, Book, BookSeries, BookSeriesLink
from library.services import find_alphabet_node_by_name, get_alphabet_tree

from .renderers import OPDSRenderer
from .serializers import (
    build_author_detail_feed,
    build_author_results_feed,
    build_author_series_feed,
    build_book_detail_feed,
    build_book_results_feed,
    build_root_feed,
    build_series_detail_feed,
    build_series_results_feed,
    build_tree_feed,
    wants_thick_entries,
)
from .throttles import OPDSDayRateThrottle, OPDSMinuteRateThrottle


class OPDSPageNumberPagination(PageNumberPagination):
    """DRF page-number paginator configured for OPDS feeds.

    Page size is controlled by ``settings.OPDS_PAGE_SIZE``
    Clients cannot override the page size.  The ``first`` link is always
    the URL with the ``page`` param removed.
    """

    page_size = settings.OPDS_PAGE_SIZE
    page_query_param = 'page'

    def get_first_link(self) -> str | None:
        """Return the URL for page 1 (``page`` param removed)."""
        if not self.page:
            return None
        url = self.request.build_absolute_uri()
        return remove_query_param(url, self.page_query_param)


class OPDSBaseView(APIView):
    """Base class for all OPDS feed views.

    Enforces the shared renderer, throttle, and permission configuration
    used across every OPDS endpoint.
    """

    renderer_classes = [OPDSRenderer]
    throttle_classes = [OPDSMinuteRateThrottle, OPDSDayRateThrottle]
    permission_classes = [AllowAny]
    pagination_class = OPDSPageNumberPagination

    def _paginate(self, queryset, request):
        """Paginate a queryset and return ``(page_items, pagination_dict)``.

        Args:
            queryset: The Django QuerySet to paginate.
            request: The current HTTP request.

        Returns:
            A 2-tuple ``(items, pagination)`` where ``items`` is the current
            page's list of objects and ``pagination`` is a dict with 'first',
            'next', and 'previous' URL strings (or None values), or None if
            pagination did not apply.
        """
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, self)
        if page is None:
            return list(queryset), None

        pagination = {
            'first': paginator.get_first_link(),
            'next': paginator.get_next_link(),
            'previous': paginator.get_previous_link(),
        }
        return page, pagination


class RootFeedView(OPDSBaseView):
    """GET opds:root/ — root navigation catalog feed.
    """

    def get(self, request):
        feed = build_root_feed(request)
        return Response(feed)


# ---------------------------------------------------------------------------
# Author views
# ---------------------------------------------------------------------------

class AuthorListFeedView(OPDSBaseView):
    """GET opds:root/authors/ — flat, paginated author navigation feed.

    Supports optional ``?filter=<prefix>`` and ``?regex=<regex>`` query
    params.  ``regex`` takes precedence when both are present.  Without
    either param the full author set is returned.
    Entries are ordered by ``last_name``, ``first_name``, ``middle_name``
    and link to the author detail feed at ``opds:root/authors/<pk>/``.
    """

    def get(self, request):
        queryset = (
            Author.objects
            .annotate(book_count=Count('books', distinct=True))
            .order_by('last_name', 'first_name', 'middle_name')
        )

        regex = request.query_params.get('regex', '')
        filter_val = request.query_params.get('filter', '')

        if regex:
            queryset = queryset.filter(last_name__iregex=regex)
        elif filter_val:
            queryset = queryset.filter(last_name__istartswith=filter_val)

        page, pagination = self._paginate(queryset, request)
        feed = build_author_results_feed(page, pagination, request)
        return Response(feed)


class AuthorTreeFeedView(OPDSBaseView):
    """GET opds:root/authors/tree/ and opds:root/authors/tree/<str:name>/.

    Serves the alphabet tree navigation feed for authors.

    Without a ``name`` segment: renders the root tree (top-level nodes only,
    no synthetic "all" entry).

    With a ``name`` segment: renders the ``name`` node's
    children with a synthetic "all <name>" entry prepended.
    """

    def get(self, request, name=None):
        tree = get_alphabet_tree(Author.objects.all(), 'last_name')

        if name is None:
            node = tree
        else:
            node = find_alphabet_node_by_name(tree, name)
            if node is None or not node.entries:
                raise Http404

        feed = build_tree_feed(node, request, base_url='authors', entity_label='Authors')
        return Response(feed)


class AuthorDetailFeedView(OPDSBaseView):
    """GET opds:root/authors/<int:pk>/ — author detail navigation feed.

    Returns exactly the author sub-feed entries
    """

    def get(self, request, pk):
        author = get_object_or_404(Author, pk=pk)
        feed = build_author_detail_feed(author, request)
        return Response(feed)


class AuthorSeriesFeedView(OPDSBaseView):
    """GET opds:root/authors/<int:pk>/series/ — author series navigation feed.

    Lists each series the author has books in, annotated with the per-author
    book count.  When the author has standalone books (books not linked to any
    series), a "Standalone Books" entry is prepended as the first entry,
    linking to ``opds:root/authors/<pk>/books/?series=none``.
    """

    def get(self, request, pk):
        author = get_object_or_404(Author, pk=pk)

        series_with_counts = (
            BookSeries.objects
            .filter(books__authors=author)
            .annotate(
                author_book_count=Count(
                    'books',
                    filter=Q(books__authors=author),
                    distinct=True,
                )
            )
            .distinct()
            .order_by('name')
        )

        standalone_count = author.books.filter(bookserieslink__isnull=True).count()

        feed = build_author_series_feed(
            author, request, series_with_counts, standalone_count
        )
        return Response(feed)


class AuthorBooksFeedView(OPDSBaseView):
    """GET opds:root/authors/<int:pk>/books/ — author books acquisition feed.

    Returns a paginated acquisition feed of all books by this author, sorted
    alphabetically by title.

    Supports optional ``?series=none`` query param: when present, filters to
    books not linked to any series (powers the "Standalone Books" category
    from the series feed).
    """

    def get(self, request, pk):
        author = get_object_or_404(Author, pk=pk)

        queryset = (
            author.books
            .prefetch_related('authors', 'bookserieslink_set__series')
            .order_by('title')
        )

        if request.query_params.get('series') == 'none':
            queryset = queryset.filter(bookserieslink__isnull=True)

        page, pagination = self._paginate(queryset, request)
        feed = build_book_results_feed(
            page,
            pagination,
            request,
            feed_id=f'tag:bookshelf:author:{author.pk}:books',
            feed_title=f'{author.full_name} — Books',
            thick=wants_thick_entries(request),
        )
        return Response(feed)


class AuthorRecentBooksFeedView(OPDSBaseView):
    """GET opds:root/authors/<int:pk>/books/recent/ — recently added books.

    Returns a paginated acquisition feed of this author's books, sorted by
    ``created_at`` descending (most recently added first).
    """

    def get(self, request, pk):
        author = get_object_or_404(Author, pk=pk)

        queryset = (
            author.books
            .prefetch_related('authors', 'bookserieslink_set__series')
            .order_by('-created_at')
        )

        page, pagination = self._paginate(queryset, request)
        feed = build_book_results_feed(
            page,
            pagination,
            request,
            feed_id=f'tag:bookshelf:author:{author.pk}:books:recent',
            feed_title=f'{author.full_name} — Recently Added',
            thick=wants_thick_entries(request),
        )
        return Response(feed)


# ---------------------------------------------------------------------------
# Series views
# ---------------------------------------------------------------------------

class SeriesListFeedView(OPDSBaseView):
    """GET opds:root/series/ — flat, paginated series navigation feed.

    Supports optional ``?filter=<prefix>`` and ``?regex=<regex>`` query
    params.  ``regex`` takes precedence when both are present.  Without either
    param the full series set is returned.  Entries are ordered by ``name`` and
    link to the series detail feed at ``opds:root/series/<pk>/``.
    """

    def get(self, request):
        queryset = (
            BookSeries.objects
            .annotate(book_count=Count('books', distinct=True))
            .order_by('name')
        )

        regex = request.query_params.get('regex', '')
        filter_val = request.query_params.get('filter', '')

        if regex:
            queryset = queryset.filter(name__iregex=regex)
        elif filter_val:
            queryset = queryset.filter(name__istartswith=filter_val)

        page, pagination = self._paginate(queryset, request)
        feed = build_series_results_feed(page, pagination, request)
        return Response(feed)


class SeriesTreeFeedView(OPDSBaseView):
    """GET opds:root/series/tree/ and opds:root/series/tree/<str:name>/.

    Serves the alphabet tree navigation feed for series.

    Without a ``name`` segment: renders the root tree (top-level nodes only,
    no synthetic "all" entry).

    With a ``name`` segment: renders the ``name`` node's children with a
    synthetic "all <name>" entry prepended.  Returns HTTP 404 when ``name``
    does not resolve to an expandable node (leaf nodes are never addressed by
    a path segment).
    """

    def get(self, request, name=None):
        tree = get_alphabet_tree(BookSeries.objects.all(), 'name')

        if name is None:
            node = tree
        else:
            node = find_alphabet_node_by_name(tree, name)
            if node is None or not node.entries:
                raise Http404

        feed = build_tree_feed(node, request, base_url='series', entity_label='Series')
        return Response(feed)


class SeriesDetailFeedView(OPDSBaseView):
    """GET opds:root/series/<int:pk>/ — series detail acquisition feed.

    Lists each direct subseries as a navigation entry (linking to
    ``opds:root/series/<subpk>/``), followed by the series' books as
    acquisition entries ordered by ``sequence_number``, each title prefixed
    ``"#<seq> · "``.  Book entries are thin by default; ``?detail=thick``
    renders the complete book shape inline (preserved across pagination).
    """

    def get(self, request, pk):
        series = get_object_or_404(BookSeries, pk=pk)

        subseries = (
            series.subseries
            .annotate(book_count=Count('books', distinct=True))
            .order_by('name')
        )

        book_links = (
            BookSeriesLink.objects
            .filter(series=series)
            .select_related('book')
            .prefetch_related('book__authors', 'book__bookserieslink_set__series')
            .order_by('sequence_number')
        )

        page, pagination = self._paginate(book_links, request)
        feed = build_series_detail_feed(
            series, subseries, page, pagination, request,
            thick=wants_thick_entries(request),
        )
        return Response(feed)


# ---------------------------------------------------------------------------
# Book views
# ---------------------------------------------------------------------------

class BookListFeedView(OPDSBaseView):
    """GET opds:root/books/ — flat, paginated book acquisition feed.

    Supports optional ``?filter=<prefix>`` and ``?regex=<regex>`` query
    params.  ``regex`` takes precedence when both are present (matching
    ``BookListView.get_queryset``).  Without either param the full book set is
    returned.  Entries are ordered by ``title`` and are thin by default;
    ``?detail=thick`` renders the complete book shape inline (the preference is
    preserved across pagination links).
    """

    def get(self, request):
        queryset = (
            Book.objects
            .prefetch_related('authors', 'bookserieslink_set__series')
            .order_by('title')
        )

        regex = request.query_params.get('regex', '')
        filter_val = request.query_params.get('filter', '')

        if regex:
            queryset = queryset.filter(title__iregex=regex)
        elif filter_val:
            queryset = queryset.filter(title__istartswith=filter_val)

        page, pagination = self._paginate(queryset, request)
        feed = build_book_results_feed(
            page, pagination, request, thick=wants_thick_entries(request)
        )
        return Response(feed)


class BookTreeFeedView(OPDSBaseView):
    """GET opds:root/books/tree/ and opds:root/books/tree/<str:name>/.

    Serves the alphabet tree navigation feed for books.

    Without a ``name`` segment: renders the root tree (top-level nodes only,
    no synthetic "all" entry).

    With a ``name`` segment: renders the ``name`` node's children with a
    synthetic "all <name>" entry prepended.  Returns HTTP 404 when ``name``
    does not resolve to an expandable node (leaf nodes are never addressed by
    a path segment).
    """

    def get(self, request, name=None):
        tree = get_alphabet_tree(Book.objects.all(), 'title')

        if name is None:
            node = tree
        else:
            node = find_alphabet_node_by_name(tree, name)
            if node is None or not node.entries:
                raise Http404

        feed = build_tree_feed(node, request)
        return Response(feed)


class BookDetailFeedView(OPDSBaseView):
    """GET opds:root/books/<int:pk>/ — complete book-detail acquisition feed.

    Renders the single complete book entry: title, sanitized-XHTML
    description, ``<calibre:series>`` metadata, cover image + thumbnail, one
    ``rel="related"`` link per author and per series, and the acquisition link.
    This feed is the ``rel="alternate"`` target referenced by thin listing
    entries, so it never carries a self-referential alternate link.
    """

    def get(self, request, pk):
        book = get_object_or_404(
            Book.objects.prefetch_related('authors', 'bookserieslink_set__series'),
            pk=pk,
        )
        feed = build_book_detail_feed(book, request)
        return Response(feed)
