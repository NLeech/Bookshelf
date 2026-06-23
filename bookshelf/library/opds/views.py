from urllib.parse import quote

from django.conf import settings
from django.db.models import Count, Exists, OuterRef, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from rest_framework.authentication import BasicAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.utils.urls import remove_query_param
from rest_framework.views import APIView

from library.models import Author, Book, BookSeries, BookSeriesLink, Genre
from library.services import (
    can_view_book,
    find_alphabet_node_by_name,
    get_alphabet_tree,
    get_book_file_content,
    get_descendants,
    search_entities,
)

from .renderers import OPDSRenderer, OpenSearchRenderer
from .serializers import (
    build_author_detail_feed,
    build_author_results_feed,
    build_author_series_feed,
    build_book_detail_feed,
    build_book_results_feed,
    build_genre_detail_feed,
    build_genre_root_feed,
    build_opensearch_description,
    build_root_feed,
    build_search_root_feed,
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

    ``authentication_classes`` is Basic-only (not Session): auth is *attempted*
    on every view so ``request.user`` is populated (browse stays ``AllowAny``),
    while a Basic-only authenticator guarantees ``401 + WWW-Authenticate: Basic``
    on the enforced views (Session-first would yield ``403`` instead).
    """

    renderer_classes = [OPDSRenderer]
    throttle_classes = [OPDSMinuteRateThrottle, OPDSDayRateThrottle]
    authentication_classes = [BasicAuthentication]
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


class OPDSLoginView(OPDSBaseView):
    """GET opds:login/ — credential challenge / redirect to the root feed.

    Anonymous requests are rejected by ``IsAuthenticated``, which makes DRF
    raise ``NotAuthenticated`` → ``401 + WWW-Authenticate: Basic`` (the
    challenge that makes a reader show its credential prompt).  Once the reader
    sends valid Basic credentials the view redirects (``302``) to the OPDS root.

    Uses ``JSONRenderer`` so DRF can render the ``401`` exception body — the
    ``OPDSRenderer`` expects a feed dict and would raise on ``{'detail': …}``;
    the success path returns a redirect that bypasses rendering.
    """

    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer]

    def get(self, request):
        return redirect('opds:root')


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
# Genre views
# ---------------------------------------------------------------------------

def _genre_book_queryset(genre):
    """Return the base Book queryset for a genre (genre + all descendants).

    Mirrors ``BookListView.get_queryset``: a book is "in" a genre when it is
    tagged with that genre or any of its (leaf) descendant genres, found via
    :func:`library.services.get_descendants`.

    Args:
        genre: A Genre model instance.

    Returns:
        A distinct ``Book`` queryset scoped to the genre and its descendants.
    """
    all_ids = {genre.pk} | get_descendants([genre.pk])
    return Book.objects.filter(genres__id__in=all_ids).distinct()


class GenreRootFeedView(OPDSBaseView):
    """GET opds:root/genres/ — top-level genre navigation feed.

    Lists every top-level genre (``parent=None``).  Each entry links to the
    genre detail feed at ``opds:root/genres/<pk>/`` and carries the genre's
    descendant-inclusive distinct book count.
    """

    def get(self, request):
        genres = Genre.objects.filter(parent=None).order_by('name')
        genres_with_counts = [
            (genre, _genre_book_queryset(genre).count())
            for genre in genres
        ]
        feed = build_genre_root_feed(genres_with_counts, request)
        return Response(feed)


class GenreDetailFeedView(OPDSBaseView):
    """GET opds:root/genres/<int:pk>/ — genre detail (subgenres-only) feed.

    Renders one navigation entry per direct subgenre, each linking to
    ``opds:root/genres/<subpk>/`` and carrying its descendant-inclusive book
    count.  When the genre has no subgenres (a leaf genre), the view issues an
    HTTP 302 redirect to ``opds:root/genres/<pk>/books/tree/`` instead (302, not
    301, because leaf-ness is data-dependent).  Returns HTTP 404 for an unknown
    genre.
    """

    def get(self, request, pk):
        genre = get_object_or_404(Genre, pk=pk)
        subgenres = genre.subgenres.order_by('name')

        if not subgenres.exists():
            return redirect('opds:genre_book_tree', pk=pk)

        subgenres_with_counts = [
            (subgenre, _genre_book_queryset(subgenre).count())
            for subgenre in subgenres
        ]
        feed = build_genre_detail_feed(genre, subgenres_with_counts, request)
        return Response(feed)


class GenreBookTreeFeedView(OPDSBaseView):
    """GET opds:root/genres/<int:pk>/books/tree/[<str:name>/].

    The standard alphabet-tree navigation feed (see docs/TDD_OPDS.md §6.2),
    built from the genre's (+descendants) book queryset so the tree only
    contains letters this genre actually has.  Child links use the
    ``genres/<pk>/books`` base, so leaves link to
    ``opds:root/genres/<pk>/books/?filter=|?regex=`` and expandable nodes to
    ``opds:root/genres/<pk>/books/tree/<name>/``.

    Without a ``name`` segment: renders the root tree.  With a ``name`` segment:
    resolves the node via ``find_alphabet_node_by_name`` (HTTP 404 when missing
    or a leaf — leaves are never addressed by a path segment).
    """

    def get(self, request, pk, name=None):
        genre = get_object_or_404(Genre, pk=pk)
        tree = get_alphabet_tree(_genre_book_queryset(genre), 'title')

        if name is None:
            node = tree
        else:
            node = find_alphabet_node_by_name(tree, name)
            if node is None or not node.entries:
                raise Http404

        feed = build_tree_feed(
            node, request,
            base_url=f'genres/{genre.pk}/books',
            entity_label=genre.name,
        )
        return Response(feed)


class GenreBookListFeedView(OPDSBaseView):
    """GET opds:root/genres/<int:pk>/books/ — flat genre book acquisition feed.

    The genre's (+descendants) book queryset, filtered by the standard
    precedence: ``?regex=`` → ``title__iregex`` (wins), elif ``?filter=`` →
    ``title__istartswith``, else the full genre set.  Always paginated and
    ordered by ``title``.  Entries are thin by default; ``?detail=thick``
    renders the complete book shape inline (preserved across pagination).
    """

    def get(self, request, pk):
        genre = get_object_or_404(Genre, pk=pk)
        queryset = (
            _genre_book_queryset(genre)
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
            page,
            pagination,
            request,
            feed_id=f'tag:bookshelf:genre:{genre.pk}:books',
            feed_title=f'{genre.name} — Books',
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


class OPDSBookDownloadView(OPDSBaseView):
    """GET opds:book_download — download a book's extracted file.

    Auth semantics: ``IsAuthenticated`` yields ``401 + WWW-Authenticate: Basic``
    for anonymous requests (inherited ``BasicAuthentication``); an authenticated
    user lacking download authorization (``can_view_book``) gets ``403``; a book
    with no readable file gets ``404``; otherwise the extracted content is
    returned as an attachment.

    Uses ``JSONRenderer`` so DRF can render the ``401``/``403`` exception bodies;
    the success body is a plain ``HttpResponse`` passed through unrendered.
    """

    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer]

    def get(self, request, pk):
        book = get_object_or_404(Book, pk=pk)

        if not can_view_book(request.user, book):
            raise PermissionDenied

        filename, content, content_type = get_book_file_content(book)
        if content is None:
            return HttpResponse(status=404)

        response = HttpResponse(content, content_type=content_type)
        response['Content-Disposition'] = _content_disposition(filename)
        return response


def _content_disposition(filename: str) -> str:
    """Build an RFC 6266 ``Content-Disposition`` attachment header.

    Mirrors Django's ``FileResponse`` behaviour used by the web
    ``BookDownloadView``: ASCII filenames use the plain ``filename="…"`` form,
    while non-ASCII filenames use the percent-encoded ``filename*=utf-8''…``
    form.
    """
    if filename.isascii():
        return f'attachment; filename="{filename}"'
    return f"attachment; filename*=utf-8''{quote(filename)}"


# ---------------------------------------------------------------------------
# Search views
# ---------------------------------------------------------------------------

class SearchRootFeedView(OPDSBaseView):
    """GET opds:root/search/?q=<query> — search section-index navigation feed.

    Searches authors, series, and books via ``library.services.search_entities``
    and emits up to three section entries (one per non-empty result set), each
    linking to its own independently paginated sub-feed.  The root feed itself
    is never paginated.  An empty or missing ``q`` (or a no-match query) yields
    a valid feed with zero entries — never an error.
    """

    def get(self, request):
        query = request.query_params.get('q', '').strip()
        results = search_entities(query)
        feed = build_search_root_feed(query, results, request)
        return Response(feed)


class SearchAuthorsFeedView(OPDSBaseView):
    """GET opds:root/search/authors/?q=<query> — paginated author search feed.

    A navigation feed of authors matching ``q``; each entry links to the author
    detail feed at ``opds:root/authors/<pk>/``.  The ``q`` param is preserved on
    pagination links.
    """

    def get(self, request):
        query = request.query_params.get('q', '').strip()
        queryset = (
            search_entities(query)['authors']
            .annotate(book_count=Count('books', distinct=True))
        )
        page, pagination = self._paginate(queryset, request)
        feed = build_author_results_feed(
            page,
            pagination,
            request,
            feed_id='tag:bookshelf:search:authors',
            feed_title=f'Search “{query}” — Authors',
        )
        return Response(feed)


class SearchSeriesFeedView(OPDSBaseView):
    """GET opds:root/search/series/?q=<query> — paginated series search feed.

    A navigation feed of series matching ``q``; each entry links to the series
    detail feed at ``opds:root/series/<pk>/``.  The ``q`` param is preserved on
    pagination links.
    """

    def get(self, request):
        query = request.query_params.get('q', '').strip()
        queryset = (
            search_entities(query)['series']
            .annotate(book_count=Count('books', distinct=True))
        )
        page, pagination = self._paginate(queryset, request)
        feed = build_series_results_feed(
            page,
            pagination,
            request,
            feed_id='tag:bookshelf:search:series',
            feed_title=f'Search “{query}” — Series',
        )
        return Response(feed)


class SearchBooksFeedView(OPDSBaseView):
    """GET opds:root/search/books/?q=<query> — paginated book search feed.

    An acquisition feed of books matching ``q``.  Entries are thin by default;
    ``?detail=thick`` renders the complete book shape inline (the preference is
    preserved across pagination links, alongside ``q``).
    """

    def get(self, request):
        query = request.query_params.get('q', '').strip()
        queryset = (
            search_entities(query)['books']
            .prefetch_related('authors', 'bookserieslink_set__series')
        )
        page, pagination = self._paginate(queryset, request)
        feed = build_book_results_feed(
            page,
            pagination,
            request,
            feed_id='tag:bookshelf:search:books',
            feed_title=f'Search “{query}” — Books',
            thick=wants_thick_entries(request),
        )
        return Response(feed)


class OpenSearchDescriptionView(OPDSBaseView):
    """GET opds:root/search/description.xml — OpenSearch description document.

    Returns the OpenSearch Description Document as
    ``application/opensearchdescription+xml`` (via ``OpenSearchRenderer``).  This
    is the descriptor referenced by ``<link rel="search"
    type="application/opensearchdescription+xml">`` in the root feed, required
    for Calibre / KOreader search auto-discovery.
    """

    renderer_classes = [OpenSearchRenderer]

    def get(self, request):
        return Response(build_opensearch_description(request))
