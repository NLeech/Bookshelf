"""
OPDS v1.2 catalog tests.
"""
import xml.etree.ElementTree as ET

from django.core.cache import cache
from django.db.models import Exists, OuterRef
from django.test import TestCase

from library.models import Author, Book, BookSeries, BookSeriesLink, Language
from library.tests.test_data_factory import create_test_dataset


class OPDSThrottleResetMixin:
    """Clear the throttle cache before each test.

    OPDS endpoints use DRF anonymous-rate throttles whose state lives in the
    shared cache and persists across tests within a run.  Clearing it in
    ``setUp`` keeps each test isolated and prevents spurious ``429`` responses
    once the cumulative request count crosses the per-minute limit.
    """

    def setUp(self):
        super().setUp()
        cache.clear()


NS = {
    'atom': 'http://www.w3.org/2005/Atom',
    'opds': 'http://opds-spec.org/2010/catalog',
    'dc':   'http://purl.org/dc/terms/',
}


def _parse(response):
    """Parse a DRF/Django test response body as an XML element tree."""
    return ET.fromstring(response.content)


class OPDSRootFeedTest(OPDSThrottleResetMixin, TestCase):
    """Tests for GET /opds/v1/ — the root navigation catalog feed.

    No database content is required; the feed is purely structural.
    """

    ROOT_URL = '/opds/v1/'

    def _get_root(self):
        """Fetch the root feed and return (response, parsed_root_element)."""
        response = self.client.get(self.ROOT_URL)
        return response, _parse(response)

    # ------------------------------------------------------------------
    # 1. Status code
    # ------------------------------------------------------------------

    def test_root_feed_status_200(self):
        response = self.client.get(self.ROOT_URL)
        self.assertEqual(response.status_code, 200)

    # ------------------------------------------------------------------
    # 2. Content-Type
    # ------------------------------------------------------------------

    def test_root_feed_content_type(self):
        response = self.client.get(self.ROOT_URL)
        self.assertTrue(
            response['Content-Type'].startswith('application/atom+xml'),
            msg=f'Unexpected Content-Type: {response["Content-Type"]}',
        )

    # ------------------------------------------------------------------
    # 3. Exactly five catalog entries
    # ------------------------------------------------------------------

    def test_root_feed_has_five_catalog_entries(self):
        _, root = self._get_root()
        entries = root.findall('atom:entry', NS)
        self.assertEqual(len(entries), 5)

    # ------------------------------------------------------------------
    # 4. Entry titles
    # ------------------------------------------------------------------

    def test_root_feed_entry_titles(self):
        _, root = self._get_root()
        entries = root.findall('atom:entry', NS)
        titles = {e.findtext('atom:title', namespaces=NS) for e in entries}
        self.assertEqual(titles, {'Authors', 'Genres', 'Series', 'Books', 'Search'})

    # ------------------------------------------------------------------
    # 5. Self link
    # ------------------------------------------------------------------

    def test_root_feed_self_link(self):
        _, root = self._get_root()
        links = root.findall('atom:link', NS)
        self_links = [
            lnk for lnk in links if lnk.get('rel') == 'self'
        ]
        self.assertEqual(len(self_links), 1, 'Expected exactly one <link rel="self">')
        href = self_links[0].get('href', '')
        self.assertTrue(
            href.endswith('/opds/v1/'),
            msg=f'Self link href {href!r} does not end with /opds/v1/',
        )

    # ------------------------------------------------------------------
    # 6. Start link
    # ------------------------------------------------------------------

    def test_root_feed_start_link(self):
        _, root = self._get_root()
        links = root.findall('atom:link', NS)
        start_links = [
            lnk for lnk in links if lnk.get('rel') == 'start'
        ]
        self.assertEqual(len(start_links), 1, 'Expected exactly one <link rel="start">')
        href = start_links[0].get('href', '')
        self.assertTrue(
            href.endswith('/opds/v1/'),
            msg=f'Start link href {href!r} does not end with /opds/v1/',
        )

    # ------------------------------------------------------------------
    # 7. Search entry has OpenSearch description link
    # ------------------------------------------------------------------

    def test_root_feed_search_entry_has_opensearch_link(self):
        _, root = self._get_root()
        entries = root.findall('atom:entry', NS)

        search_entry = None
        for entry in entries:
            if entry.findtext('atom:title', namespaces=NS) == 'Search':
                search_entry = entry
                break

        self.assertIsNotNone(search_entry, 'No Search entry found in root feed')

        links = search_entry.findall('atom:link', NS)
        opensearch_links = [
            lnk for lnk in links
            if lnk.get('type') == 'application/opensearchdescription+xml'
        ]
        self.assertEqual(
            len(opensearch_links), 1,
            'Search entry must have exactly one '
            '<link type="application/opensearchdescription+xml">',
        )

    # ------------------------------------------------------------------
    # 8. Pretty-printed XML (human-readable output)
    # ------------------------------------------------------------------

    def test_root_feed_is_pretty_printed(self):
        response = self.client.get(self.ROOT_URL)
        self.assertIn(b'\n', response.content, 'XML output should contain newlines')
        self.assertIn(b'  <', response.content, 'XML output should contain indentation')


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _get_entry_titles(root_el):
    """Return an ordered list of <title> texts from all <entry> elements."""
    return [
        e.findtext('atom:title', namespaces=NS)
        for e in root_el.findall('atom:entry', NS)
    ]


def _get_link_hrefs(element, rel):
    """Return all href values for <link rel="…"> children of *element*."""
    return [
        lnk.get('href', '')
        for lnk in element.findall('atom:link', NS)
        if lnk.get('rel') == rel
    ]


def _count_all_pages(client, url):
    """Follow pagination and return the total entry count across all pages."""
    total = 0
    while url:
        response = client.get(url)
        root_el = _parse(response)
        total += len(root_el.findall('atom:entry', NS))
        next_links = _get_link_hrefs(root_el, 'next')
        url = next_links[0] if next_links else None
    return total


# ---------------------------------------------------------------------------
# OPDSAuthorListFeedTest
# ---------------------------------------------------------------------------

class OPDSAuthorListFeedTest(OPDSThrottleResetMixin, TestCase):
    """Tests for the author alphabet-tree root and flat results endpoints.

    Fixture: canonical dataset (255 authors: A=137, B=58, C=19, etc.).
    """

    @classmethod
    def setUpTestData(cls):
        create_test_dataset()

    def test_author_alphabet_root_has_a_entry(self):
        """GET /opds/v1/authors/tree/ → feed contains entry for 'A' with count 137."""
        response = self.client.get('/opds/v1/authors/tree/')
        self.assertEqual(response.status_code, 200)
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        titles = [e.findtext('atom:title', namespaces=NS) for e in entries]
        self.assertIn('A', titles)
        a_entry = next(e for e in entries if e.findtext('atom:title', namespaces=NS) == 'A')
        content = a_entry.findtext('atom:content', namespaces=NS)
        self.assertIn('137', content)

    def test_author_alphabet_root_has_b_entry(self):
        """GET /opds/v1/authors/tree/ → feed contains entry for 'B' with count 58."""
        response = self.client.get('/opds/v1/authors/tree/')
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        titles = [e.findtext('atom:title', namespaces=NS) for e in entries]
        self.assertIn('B', titles)
        b_entry = next(e for e in entries if e.findtext('atom:title', namespaces=NS) == 'B')
        content = b_entry.findtext('atom:content', namespaces=NS)
        self.assertIn('58', content)

    def test_author_alphabet_root_no_entry_for_missing_letter(self):
        """GET /opds/v1/authors/tree/ → feed does NOT contain a 'Z' or 'z' root entry.

        'Z' authors exist but their count is below min_first_level_quantity
        so they are demoted into the 'Other' node, not placed at root.
        """
        response = self.client.get('/opds/v1/authors/tree/')
        root = _parse(response)
        titles = _get_entry_titles(root)
        self.assertNotIn('Z', titles)
        self.assertNotIn('z', titles)

    def test_author_results_by_filter_status_200(self):
        """GET /opds/v1/authors/?filter=b → HTTP 200."""
        response = self.client.get('/opds/v1/authors/?filter=b')
        self.assertEqual(response.status_code, 200)

    def test_author_results_by_filter_has_correct_count(self):
        """GET /opds/v1/authors/?filter=b → exactly 20 entries (page 1 of 58)."""
        response = self.client.get('/opds/v1/authors/?filter=b')
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        self.assertEqual(len(entries), 20)

    def test_author_results_entry_links_to_author_detail(self):
        """Each entry in /opds/v1/authors/?filter=b links to /opds/v1/authors/<pk>/."""
        response = self.client.get('/opds/v1/authors/?filter=b')
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        self.assertGreater(len(entries), 0, 'Expected at least one entry')
        for entry in entries:
            links = entry.findall('atom:link', NS)
            hrefs = [lnk.get('href', '') for lnk in links]
            self.assertTrue(
                any('/opds/v1/authors/' in h and h.rstrip('/').split('/')[-1].isdigit() for h in hrefs),
                msg=f'Entry links {hrefs!r} do not point to an author detail URL',
            )

    def test_author_results_filter_not_found_returns_empty_feed(self):
        """GET /opds/v1/authors/?filter=y → HTTP 200 with zero entries."""
        response = self.client.get('/opds/v1/authors/?filter=y')
        self.assertEqual(response.status_code, 200)
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        self.assertEqual(len(entries), 0)

    def test_author_results_sorted_alphabetically(self):
        """Entries in /opds/v1/authors/?filter=b are in ascending last_name order."""
        response = self.client.get('/opds/v1/authors/?filter=b')
        root = _parse(response)
        titles = _get_entry_titles(root)
        self.assertEqual(titles, sorted(titles, key=str.lower))

    def test_author_digits_node_list(self):
        """GET /opds/v1/authors/?regex=^[0-9] → 200 with exactly 12 entries."""
        response = self.client.get('/opds/v1/authors/?regex=^[0-9]')
        self.assertEqual(response.status_code, 200)
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        self.assertEqual(len(entries), 12)

    def test_author_list_is_navigation_feed(self):
        """GET /opds/v1/authors/?filter=b → Content-Type contains kind=navigation."""
        response = self.client.get('/opds/v1/authors/?filter=b')
        self.assertIn('kind=navigation', response['Content-Type'])

    def test_author_tree_is_navigation_feed(self):
        """GET /opds/v1/authors/tree/ → Content-Type contains kind=navigation."""
        response = self.client.get('/opds/v1/authors/tree/')
        self.assertIn('kind=navigation', response['Content-Type'])

    def test_author_tree_node_status_200(self):
        """GET /opds/v1/authors/tree/a/ → HTTP 200 (expandable node)."""
        response = self.client.get('/opds/v1/authors/tree/a/')
        self.assertEqual(response.status_code, 200)

    def test_author_tree_leaf_node_returns_404(self):
        """GET /opds/v1/authors/tree/c/ → HTTP 404 (C=19 is a leaf, no children)."""
        # C=19 < min_quantity=50 so the C node has no children → leaf → 404.
        response = self.client.get('/opds/v1/authors/tree/c/')
        self.assertEqual(response.status_code, 404)

    def test_author_tree_nonexistent_node_returns_404(self):
        """GET /opds/v1/authors/tree/z/ → HTTP 404 (no Z node at root level)."""
        response = self.client.get('/opds/v1/authors/tree/z/')
        self.assertEqual(response.status_code, 404)

    def test_author_tree_sub_node_has_all_entry_first(self):
        """GET /opds/v1/authors/tree/a/ → first entry is 'all a'."""
        response = self.client.get('/opds/v1/authors/tree/a/')
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        first_title = entries[0].findtext('atom:title', namespaces=NS)
        self.assertEqual(first_title, 'all a')

    def test_author_tree_sub_node_all_entry_links_to_filter(self):
        """'all a' entry in /opds/v1/authors/tree/a/ links to ?filter=a."""
        response = self.client.get('/opds/v1/authors/tree/a/')
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        all_entry = entries[0]
        hrefs = [lnk.get('href', '') for lnk in all_entry.findall('atom:link', NS)]
        self.assertTrue(
            any('?filter=a' in h for h in hrefs),
            msg=f'Expected ?filter=a in hrefs: {hrefs}',
        )

    def test_author_full_set_no_filter_returns_paginated_results(self):
        """GET /opds/v1/authors/ (no params) → 200 with entries (full set, first page)."""
        response = self.client.get('/opds/v1/authors/')
        self.assertEqual(response.status_code, 200)
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        self.assertEqual(len(entries), 20)


# ---------------------------------------------------------------------------
# OPDSAuthorDetailTest
# ---------------------------------------------------------------------------

class OPDSAuthorDetailTest(OPDSThrottleResetMixin, TestCase):
    """Tests for the author detail and per-author sub-feed endpoints.

    Fixture: canonical dataset.
    ``author_with_series`` has at least one series book AND one standalone
    book.  ``author_standalone_only`` has only standalone books.
    """

    @classmethod
    def setUpTestData(cls):
        create_test_dataset()

        # Any author that has books (used for generic tests).
        cls.any_author = Author.objects.filter(
            Exists(Book.objects.filter(authors=OuterRef('pk')))
        ).first()

        # Author with both series-linked and standalone books.
        cls.author_with_series = (
            Author.objects
            .filter(
                Exists(
                    Book.objects.filter(
                        authors=OuterRef('pk'),
                        bookserieslink__isnull=False,
                    )
                )
            )
            .filter(
                Exists(
                    Book.objects.filter(
                        authors=OuterRef('pk'),
                        bookserieslink__isnull=True,
                    )
                )
            )
            .first()
        )

        # Author whose every book is standalone (no series links).
        cls.author_standalone_only = (
            Author.objects
            .filter(
                Exists(
                    Book.objects.filter(
                        authors=OuterRef('pk'),
                        bookserieslink__isnull=True,
                    )
                )
            )
            .exclude(
                Exists(
                    Book.objects.filter(
                        authors=OuterRef('pk'),
                        bookserieslink__isnull=False,
                    )
                )
            )
            .first()
        )

    # ------------------------------------------------------------------
    # /opds/v1/authors/<pk>/
    # ------------------------------------------------------------------

    def test_author_detail_status_200(self):
        """GET /opds/v1/authors/<pk>/ → HTTP 200."""
        response = self.client.get(f'/opds/v1/authors/{self.any_author.pk}/')
        self.assertEqual(response.status_code, 200)

    def test_author_detail_404(self):
        """GET /opds/v1/authors/99999/ → HTTP 404."""
        response = self.client.get('/opds/v1/authors/99999/')
        self.assertEqual(response.status_code, 404)

    def test_author_detail_has_three_sub_feeds(self):
        """Author detail feed has exactly 3 entries with the expected titles."""
        response = self.client.get(f'/opds/v1/authors/{self.any_author.pk}/')
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        self.assertEqual(len(entries), 3)
        titles = {e.findtext('atom:title', namespaces=NS) for e in entries}
        self.assertEqual(titles, {'All Books (A–Z)', 'Recently Added', 'Books by Series'})

    def test_author_detail_is_navigation_feed(self):
        """Author detail Content-Type contains kind=navigation."""
        response = self.client.get(f'/opds/v1/authors/{self.any_author.pk}/')
        self.assertIn('kind=navigation', response['Content-Type'])

    # ------------------------------------------------------------------
    # /opds/v1/authors/<pk>/books/
    # ------------------------------------------------------------------

    def test_author_detail_sub_feed_books_alpha_status_200(self):
        """GET /opds/v1/authors/<pk>/books/ → HTTP 200."""
        response = self.client.get(f'/opds/v1/authors/{self.any_author.pk}/books/')
        self.assertEqual(response.status_code, 200)

    def test_author_detail_sub_feed_books_alpha_is_acquisition(self):
        """Author books feed Content-Type contains kind=acquisition."""
        response = self.client.get(f'/opds/v1/authors/{self.any_author.pk}/books/')
        self.assertIn('kind=acquisition', response['Content-Type'])

    def test_author_detail_sub_feed_books_alpha_contains_author_books(self):
        """Total entry count across all pages equals author.books.count()."""
        expected = self.any_author.books.count()
        total = _count_all_pages(
            self.client,
            f'/opds/v1/authors/{self.any_author.pk}/books/',
        )
        self.assertEqual(total, expected)

    def test_author_detail_sub_feed_books_alpha_excludes_other_author(self):
        """Author books feed does NOT contain a book that belongs only to a different author."""
        # Find a book NOT by any_author.
        other_book = (
            Book.objects
            .exclude(authors=self.any_author)
            .first()
        )
        if other_book is None:
            self.skipTest('No book found that excludes any_author')

        total = _count_all_pages(
            self.client,
            f'/opds/v1/authors/{self.any_author.pk}/books/',
        )
        all_pks_in_feed = set()
        url = f'/opds/v1/authors/{self.any_author.pk}/books/'
        while url:
            root_el = _parse(self.client.get(url))
            for entry in root_el.findall('atom:entry', NS):
                entry_id = entry.findtext('atom:id', namespaces=NS) or ''
                # IDs are tag:bookshelf:book:<pk>
                pk_str = entry_id.split(':')[-1]
                if pk_str.isdigit():
                    all_pks_in_feed.add(int(pk_str))
            next_links = _get_link_hrefs(root_el, 'next')
            url = next_links[0] if next_links else None

        self.assertNotIn(other_book.pk, all_pks_in_feed)

    def test_author_detail_sub_feed_books_alpha_sorted(self):
        """Entries in the first page of author books are sorted by title ascending."""
        response = self.client.get(f'/opds/v1/authors/{self.any_author.pk}/books/')
        root = _parse(response)
        titles = _get_entry_titles(root)
        self.assertEqual(titles, sorted(titles, key=str.lower))

    # ------------------------------------------------------------------
    # /opds/v1/authors/<pk>/books/recent/
    # ------------------------------------------------------------------

    def test_author_detail_sub_feed_books_recent_status_200(self):
        """GET /opds/v1/authors/<pk>/books/recent/ → HTTP 200."""
        response = self.client.get(f'/opds/v1/authors/{self.any_author.pk}/books/recent/')
        self.assertEqual(response.status_code, 200)

    def test_author_detail_sub_feed_books_recent_sorted_by_date(self):
        """First entry <updated> >= second entry <updated> in recent books feed."""
        response = self.client.get(f'/opds/v1/authors/{self.any_author.pk}/books/recent/')
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        if len(entries) < 2:
            self.skipTest('Author has fewer than 2 books; sort order cannot be verified')
        updated_0 = entries[0].findtext('atom:updated', namespaces=NS) or ''
        updated_1 = entries[1].findtext('atom:updated', namespaces=NS) or ''
        self.assertGreaterEqual(updated_0, updated_1)

    # ------------------------------------------------------------------
    # /opds/v1/authors/<pk>/series/
    # ------------------------------------------------------------------

    def test_author_detail_sub_feed_series_status_200(self):
        """GET /opds/v1/authors/<pk>/series/ → HTTP 200."""
        response = self.client.get(f'/opds/v1/authors/{self.any_author.pk}/series/')
        self.assertEqual(response.status_code, 200)

    def test_author_detail_sub_feed_series_is_navigation(self):
        """Author series feed Content-Type contains kind=navigation."""
        response = self.client.get(f'/opds/v1/authors/{self.any_author.pk}/series/')
        self.assertIn('kind=navigation', response['Content-Type'])

    def test_author_detail_sub_feed_series_has_series(self):
        """For author_with_series: series feed has at least one entry linking to /opds/v1/series/<pk>/."""
        self.assertIsNotNone(
            self.author_with_series,
            'Canonical dataset should contain an author with series books',
        )
        response = self.client.get(f'/opds/v1/authors/{self.author_with_series.pk}/series/')
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        series_entries = [
            e for e in entries
            if any(
                '/opds/v1/series/' in lnk.get('href', '')
                for lnk in e.findall('atom:link', NS)
            )
        ]
        self.assertGreater(len(series_entries), 0)

    def test_author_detail_sub_feed_series_entry_has_book_count(self):
        """Series entry <content> contains a positive integer (book count)."""
        self.assertIsNotNone(self.author_with_series)
        response = self.client.get(f'/opds/v1/authors/{self.author_with_series.pk}/series/')
        root = _parse(response)
        series_entries = [
            e for e in root.findall('atom:entry', NS)
            if any(
                '/opds/v1/series/' in lnk.get('href', '')
                for lnk in e.findall('atom:link', NS)
            )
        ]
        self.assertGreater(len(series_entries), 0)
        for entry in series_entries:
            content = entry.findtext('atom:content', namespaces=NS) or ''
            # content must contain at least one digit
            self.assertTrue(
                any(ch.isdigit() for ch in content),
                msg=f'Series entry content {content!r} has no digit',
            )

    def test_author_detail_sub_feed_series_no_standalone_entry_when_none(self):
        """An author with no standalone books has no 'Standalone Books' entry."""
        self.assertIsNotNone(
            self.author_standalone_only,
            'Canonical dataset should contain an author with only standalone books',
        )
        # author_standalone_only has only standalone books by definition;
        # flip: we need an author with NO standalone books (all in series).
        author_all_series = (
            Author.objects
            .filter(
                Exists(
                    Book.objects.filter(
                        authors=OuterRef('pk'),
                        bookserieslink__isnull=False,
                    )
                )
            )
            .exclude(
                Exists(
                    Book.objects.filter(
                        authors=OuterRef('pk'),
                        bookserieslink__isnull=True,
                    )
                )
            )
            .first()
        )
        if author_all_series is None:
            self.skipTest('No author found with exclusively series books in canonical dataset')

        response = self.client.get(f'/opds/v1/authors/{author_all_series.pk}/series/')
        root = _parse(response)
        titles = _get_entry_titles(root)
        self.assertNotIn('Standalone Books', titles)

    def test_author_detail_sub_feed_series_has_standalone_entry_first(self):
        """For author_with_series the first entry is 'Standalone Books'."""
        self.assertIsNotNone(self.author_with_series)
        response = self.client.get(f'/opds/v1/authors/{self.author_with_series.pk}/series/')
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        first_title = entries[0].findtext('atom:title', namespaces=NS)
        self.assertEqual(first_title, 'Standalone Books')

    def test_author_detail_sub_feed_series_standalone_entry_links_to_series_none(self):
        """'Standalone Books' entry links to /opds/v1/authors/<pk>/books/?series=none."""
        self.assertIsNotNone(self.author_with_series)
        response = self.client.get(f'/opds/v1/authors/{self.author_with_series.pk}/series/')
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        standalone_entry = next(
            (e for e in entries if e.findtext('atom:title', namespaces=NS) == 'Standalone Books'),
            None,
        )
        self.assertIsNotNone(standalone_entry, 'Standalone Books entry not found')
        hrefs = [lnk.get('href', '') for lnk in standalone_entry.findall('atom:link', NS)]
        self.assertTrue(
            any(f'/opds/v1/authors/{self.author_with_series.pk}/books/?series=none' in h for h in hrefs),
            msg=f'Expected ?series=none href in {hrefs}',
        )

    def test_author_detail_sub_feed_series_standalone_entry_has_count(self):
        """'Standalone Books' entry <content> contains the correct standalone book count."""
        self.assertIsNotNone(self.author_with_series)
        expected_count = self.author_with_series.books.filter(
            bookserieslink__isnull=True,
        ).count()
        self.assertGreater(expected_count, 0)

        response = self.client.get(f'/opds/v1/authors/{self.author_with_series.pk}/series/')
        root = _parse(response)
        standalone_entry = next(
            (
                e for e in root.findall('atom:entry', NS)
                if e.findtext('atom:title', namespaces=NS) == 'Standalone Books'
            ),
            None,
        )
        self.assertIsNotNone(standalone_entry)
        content = standalone_entry.findtext('atom:content', namespaces=NS) or ''
        self.assertIn(str(expected_count), content)

    def test_author_books_series_none_filter_only_standalone(self):
        """GET /opds/v1/authors/<pk>/books/?series=none → only standalone books."""
        self.assertIsNotNone(self.author_with_series)
        expected = self.author_with_series.books.filter(
            bookserieslink__isnull=True,
        ).count()
        self.assertGreater(expected, 0)

        total = _count_all_pages(
            self.client,
            f'/opds/v1/authors/{self.author_with_series.pk}/books/?series=none',
        )
        self.assertEqual(total, expected)

    # ------------------------------------------------------------------
    # Acquisition links
    # ------------------------------------------------------------------

    def test_author_books_acquisition_link_always_rendered(self):
        """GET /opds/v1/authors/<pk>/books/ → every entry has one acquisition link.

        The catalog is fully browsable for anonymous callers; download
        permission is enforced at the download endpoint, not in the feed.
        """
        response = self.client.get(f'/opds/v1/authors/{self.any_author.pk}/books/')
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        for entry in entries:
            acq_links = [
                lnk for lnk in entry.findall('atom:link', NS)
                if lnk.get('rel') == 'http://opds-spec.org/acquisition'
            ]
            self.assertEqual(len(acq_links), 1, 'Every entry should expose an acquisition link')
            self.assertTrue(acq_links[0].get('href', '').endswith('/download/'))

    def test_author_books_acquisition_type_matches_file_type(self):
        """Acquisition link ``type`` reflects each book's ``file_type``.

        Desktop OPDS readers filter out entries whose acquisition link
        advertises a generic type, so the per-format MIME type
        (e.g. ``application/epub+zip``) must be exposed.
        """
        books = list(self.any_author.books.order_by('pk'))
        expected = {}
        for i, book in enumerate(books):
            file_type = 'epub' if i % 2 == 0 else 'fb2'
            book.file_type = file_type
            book.save(update_fields=['file_type'])
            expected_type = (
                'application/epub+zip' if file_type == 'epub'
                else 'application/x-fictionbook+xml'
            )
            expected[f'tag:bookshelf:book:{book.pk}'] = expected_type

        response = self.client.get(f'/opds/v1/authors/{self.any_author.pk}/books/')
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        for entry in entries:
            entry_id = entry.findtext('atom:id', namespaces=NS)
            acq_link = next(
                lnk for lnk in entry.findall('atom:link', NS)
                if lnk.get('rel') == 'http://opds-spec.org/acquisition'
            )
            self.assertEqual(acq_link.get('type'), expected[entry_id])

    def test_author_books_acquisition_type_defaults_for_unknown_format(self):
        """Unknown/blank ``file_type`` falls back to ``application/octet-stream``."""
        response = self.client.get(f'/opds/v1/authors/{self.any_author.pk}/books/')
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        for entry in entries:
            acq_link = next(
                lnk for lnk in entry.findall('atom:link', NS)
                if lnk.get('rel') == 'http://opds-spec.org/acquisition'
            )
            self.assertEqual(acq_link.get('type'), 'application/octet-stream')
