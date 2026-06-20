"""
OPDS v1.2 catalog tests.
"""
import io
import xml.etree.ElementTree as ET

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.db.models import Exists, OuterRef
from django.test import TestCase
from PIL import Image

from bookshelf.tests.base_test import BaseTestCase
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
    'xhtml': 'http://www.w3.org/1999/xhtml',
    'calibre': 'http://calibre.kovidgoyal.net/2009/metadata',
}

# Absolute base path of the OPDS catalog (the ``opds:root`` route).  Every
# request path and link assertion below is built from this single constant.
OPDS_BASE = '/opds/v1/'

# Static asset paths as they appear (URL-encoded) in feed hrefs.
LOGO_HREF_SUFFIX = '/static/img/Logo%2064x64x8.png'
THUMBNAIL_REL = 'http://opds-spec.org/image/thumbnail'
IMAGE_REL = 'http://opds-spec.org/image'
ACQUISITION_REL = 'http://opds-spec.org/acquisition'


def _entry_link_rels(entry):
    """Return the set of ``rel`` values on an entry's <link> children."""
    return {lnk.get('rel') for lnk in entry.findall('atom:link', NS)}


def _links_by_rel(entry, rel):
    """Return all <link> elements on *entry* with the given *rel*."""
    return [lnk for lnk in entry.findall('atom:link', NS) if lnk.get('rel') == rel]


def _parse(response):
    """Parse a DRF/Django test response body as an XML element tree."""
    return ET.fromstring(response.content)


class OPDSRootFeedTest(OPDSThrottleResetMixin, TestCase):
    """Tests for GET opds:root — the root navigation catalog feed.

    No database content is required; the feed is purely structural.
    """

    ROOT_URL = OPDS_BASE

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
            href.endswith(OPDS_BASE),
            msg=f'Self link href {href!r} does not end with {OPDS_BASE}',
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
            href.endswith(OPDS_BASE),
            msg=f'Start link href {href!r} does not end with {OPDS_BASE}',
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
        """GET opds:root/authors/tree/ → feed contains entry for 'A' with count 137."""
        response = self.client.get(f'{OPDS_BASE}authors/tree/')
        self.assertEqual(response.status_code, 200)
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        titles = [e.findtext('atom:title', namespaces=NS) for e in entries]
        self.assertIn('A', titles)
        a_entry = next(e for e in entries if e.findtext('atom:title', namespaces=NS) == 'A')
        content = a_entry.findtext('atom:content', namespaces=NS)
        self.assertIn('137', content)

    def test_author_alphabet_root_has_b_entry(self):
        """GET opds:root/authors/tree/ → feed contains entry for 'B' with count 58."""
        response = self.client.get(f'{OPDS_BASE}authors/tree/')
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        titles = [e.findtext('atom:title', namespaces=NS) for e in entries]
        self.assertIn('B', titles)
        b_entry = next(e for e in entries if e.findtext('atom:title', namespaces=NS) == 'B')
        content = b_entry.findtext('atom:content', namespaces=NS)
        self.assertIn('58', content)

    def test_author_alphabet_root_no_entry_for_missing_letter(self):
        """GET opds:root/authors/tree/ → feed does NOT contain a 'Z' or 'z' root entry.

        'Z' authors exist but their count is below min_first_level_quantity
        so they are demoted into the 'Other' node, not placed at root.
        """
        response = self.client.get(f'{OPDS_BASE}authors/tree/')
        root = _parse(response)
        titles = _get_entry_titles(root)
        self.assertNotIn('Z', titles)
        self.assertNotIn('z', titles)

    def test_author_results_by_filter_status_200(self):
        """GET opds:root/authors/?filter=b → HTTP 200."""
        response = self.client.get(f'{OPDS_BASE}authors/?filter=b')
        self.assertEqual(response.status_code, 200)

    def test_author_results_by_filter_has_correct_count(self):
        """GET opds:root/authors/?filter=b → exactly 20 entries (page 1 of 58)."""
        response = self.client.get(f'{OPDS_BASE}authors/?filter=b')
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        self.assertEqual(len(entries), 20)

    def test_author_results_entry_links_to_author_detail(self):
        """Each entry in opds:root/authors/?filter=b links to opds:root/authors/<pk>/."""
        response = self.client.get(f'{OPDS_BASE}authors/?filter=b')
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        self.assertGreater(len(entries), 0, 'Expected at least one entry')
        for entry in entries:
            links = entry.findall('atom:link', NS)
            hrefs = [lnk.get('href', '') for lnk in links]
            self.assertTrue(
                any(f'{OPDS_BASE}authors/' in h and h.rstrip('/').split('/')[-1].isdigit() for h in hrefs),
                msg=f'Entry links {hrefs!r} do not point to an author detail URL',
            )

    def test_author_results_filter_not_found_returns_empty_feed(self):
        """GET opds:root/authors/?filter=y → HTTP 200 with zero entries."""
        response = self.client.get(f'{OPDS_BASE}authors/?filter=y')
        self.assertEqual(response.status_code, 200)
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        self.assertEqual(len(entries), 0)

    def test_author_results_sorted_alphabetically(self):
        """Entries in opds:root/authors/?filter=b are in ascending last_name order."""
        response = self.client.get(f'{OPDS_BASE}authors/?filter=b')
        root = _parse(response)
        titles = _get_entry_titles(root)
        self.assertEqual(titles, sorted(titles, key=str.lower))

    def test_author_digits_node_list(self):
        """GET opds:root/authors/?regex=^[0-9] → 200 with exactly 12 entries."""
        response = self.client.get(f'{OPDS_BASE}authors/?regex=^[0-9]')
        self.assertEqual(response.status_code, 200)
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        self.assertEqual(len(entries), 12)

    def test_author_results_entry_content_has_book_count(self):
        """Each opds:root/authors/?filter=b entry <content> carries its book count."""
        response = self.client.get(f'{OPDS_BASE}authors/?filter=b')
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        for entry in entries:
            entry_id = entry.findtext('atom:id', namespaces=NS) or ''
            pk = int(entry_id.split(':')[-1])
            expected = Author.objects.get(pk=pk).books.count()
            content = entry.findtext('atom:content', namespaces=NS) or ''
            self.assertEqual(content, f'{expected} books')

    def test_author_list_is_navigation_feed(self):
        """GET opds:root/authors/?filter=b → Content-Type contains kind=navigation."""
        response = self.client.get(f'{OPDS_BASE}authors/?filter=b')
        self.assertIn('kind=navigation', response['Content-Type'])

    def test_author_tree_is_navigation_feed(self):
        """GET opds:root/authors/tree/ → Content-Type contains kind=navigation."""
        response = self.client.get(f'{OPDS_BASE}authors/tree/')
        self.assertIn('kind=navigation', response['Content-Type'])

    def test_author_tree_node_status_200(self):
        """GET opds:root/authors/tree/a/ → HTTP 200 (expandable node)."""
        response = self.client.get(f'{OPDS_BASE}authors/tree/a/')
        self.assertEqual(response.status_code, 200)

    def test_author_tree_leaf_node_returns_404(self):
        """GET opds:root/authors/tree/c/ → HTTP 404 (C=19 is a leaf, no children)."""
        # C=19 < min_quantity=50 so the C node has no children → leaf → 404.
        response = self.client.get(f'{OPDS_BASE}authors/tree/c/')
        self.assertEqual(response.status_code, 404)

    def test_author_tree_nonexistent_node_returns_404(self):
        """GET opds:root/authors/tree/z/ → HTTP 404 (no Z node at root level)."""
        response = self.client.get(f'{OPDS_BASE}authors/tree/z/')
        self.assertEqual(response.status_code, 404)

    def test_author_tree_sub_node_has_all_entry_first(self):
        """GET opds:root/authors/tree/a/ → first entry is 'all a'."""
        response = self.client.get(f'{OPDS_BASE}authors/tree/a/')
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        first_title = entries[0].findtext('atom:title', namespaces=NS)
        self.assertEqual(first_title, 'all a')

    def test_author_tree_sub_node_all_entry_links_to_filter(self):
        """'all a' entry in opds:root/authors/tree/a/ links to ?filter=a."""
        response = self.client.get(f'{OPDS_BASE}authors/tree/a/')
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        all_entry = entries[0]
        hrefs = [lnk.get('href', '') for lnk in all_entry.findall('atom:link', NS)]
        self.assertTrue(
            any('?filter=a' in h for h in hrefs),
            msg=f'Expected ?filter=a in hrefs: {hrefs}',
        )

    def test_author_full_set_no_filter_returns_paginated_results(self):
        """GET opds:root/authors/ (no params) → 200 with entries (full set, first page)."""
        response = self.client.get(f'{OPDS_BASE}authors/')
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
    # opds:root/authors/<pk>/
    # ------------------------------------------------------------------

    def test_author_detail_status_200(self):
        """GET opds:root/authors/<pk>/ → HTTP 200."""
        response = self.client.get(f'{OPDS_BASE}authors/{self.any_author.pk}/')
        self.assertEqual(response.status_code, 200)

    def test_author_detail_404(self):
        """GET opds:root/authors/99999/ → HTTP 404."""
        response = self.client.get(f'{OPDS_BASE}authors/99999/')
        self.assertEqual(response.status_code, 404)

    def test_author_detail_has_three_sub_feeds(self):
        """Author detail feed has exactly 3 entries with the expected titles."""
        response = self.client.get(f'{OPDS_BASE}authors/{self.any_author.pk}/')
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        self.assertEqual(len(entries), 3)
        titles = {e.findtext('atom:title', namespaces=NS) for e in entries}
        self.assertEqual(titles, {'Books by Title', 'New Arrivals', 'Books by Series'})

    def test_author_detail_sub_feed_titles_match(self):
        """Sub-feed titles are the spec wording in order; legacy labels absent."""
        response = self.client.get(f'{OPDS_BASE}authors/{self.any_author.pk}/')
        root = _parse(response)
        titles = _get_entry_titles(root)
        self.assertEqual(titles, ['Books by Title', 'New Arrivals', 'Books by Series'])
        self.assertNotIn('All Books (A–Z)', titles)
        self.assertNotIn('Recently Added', titles)

    def test_author_detail_is_navigation_feed(self):
        """Author detail Content-Type contains kind=navigation."""
        response = self.client.get(f'{OPDS_BASE}authors/{self.any_author.pk}/')
        self.assertIn('kind=navigation', response['Content-Type'])

    # ------------------------------------------------------------------
    # opds:root/authors/<pk>/books/
    # ------------------------------------------------------------------

    def test_author_detail_sub_feed_books_alpha_status_200(self):
        """GET opds:root/authors/<pk>/books/ → HTTP 200."""
        response = self.client.get(f'{OPDS_BASE}authors/{self.any_author.pk}/books/')
        self.assertEqual(response.status_code, 200)

    def test_author_detail_sub_feed_books_alpha_is_acquisition(self):
        """Author books feed Content-Type contains kind=acquisition."""
        response = self.client.get(f'{OPDS_BASE}authors/{self.any_author.pk}/books/')
        self.assertIn('kind=acquisition', response['Content-Type'])

    def test_author_detail_sub_feed_books_alpha_contains_author_books(self):
        """Total entry count across all pages equals author.books.count()."""
        expected = self.any_author.books.count()
        total = _count_all_pages(
            self.client,
            f'{OPDS_BASE}authors/{self.any_author.pk}/books/',
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
            f'{OPDS_BASE}authors/{self.any_author.pk}/books/',
        )
        all_pks_in_feed = set()
        url = f'{OPDS_BASE}authors/{self.any_author.pk}/books/'
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
        response = self.client.get(f'{OPDS_BASE}authors/{self.any_author.pk}/books/')
        root = _parse(response)
        titles = _get_entry_titles(root)
        self.assertEqual(titles, sorted(titles, key=str.lower))

    # ------------------------------------------------------------------
    # opds:root/authors/<pk>/books/recent/
    # ------------------------------------------------------------------

    def test_author_detail_sub_feed_books_recent_status_200(self):
        """GET opds:root/authors/<pk>/books/recent/ → HTTP 200."""
        response = self.client.get(f'{OPDS_BASE}authors/{self.any_author.pk}/books/recent/')
        self.assertEqual(response.status_code, 200)

    def test_author_detail_sub_feed_books_recent_sorted_by_date(self):
        """First entry <updated> >= second entry <updated> in recent books feed."""
        response = self.client.get(f'{OPDS_BASE}authors/{self.any_author.pk}/books/recent/')
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        if len(entries) < 2:
            self.skipTest('Author has fewer than 2 books; sort order cannot be verified')
        updated_0 = entries[0].findtext('atom:updated', namespaces=NS) or ''
        updated_1 = entries[1].findtext('atom:updated', namespaces=NS) or ''
        self.assertGreaterEqual(updated_0, updated_1)

    # ------------------------------------------------------------------
    # opds:root/authors/<pk>/series/
    # ------------------------------------------------------------------

    def test_author_detail_sub_feed_series_status_200(self):
        """GET opds:root/authors/<pk>/series/ → HTTP 200."""
        response = self.client.get(f'{OPDS_BASE}authors/{self.any_author.pk}/series/')
        self.assertEqual(response.status_code, 200)

    def test_author_detail_sub_feed_series_is_navigation(self):
        """Author series feed Content-Type contains kind=navigation."""
        response = self.client.get(f'{OPDS_BASE}authors/{self.any_author.pk}/series/')
        self.assertIn('kind=navigation', response['Content-Type'])

    def test_author_detail_sub_feed_series_has_series(self):
        """For author_with_series: series feed has at least one entry linking to opds:root/series/<pk>/."""
        self.assertIsNotNone(
            self.author_with_series,
            'Canonical dataset should contain an author with series books',
        )
        response = self.client.get(f'{OPDS_BASE}authors/{self.author_with_series.pk}/series/')
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        series_entries = [
            e for e in entries
            if any(
                f'{OPDS_BASE}series/' in lnk.get('href', '')
                for lnk in e.findall('atom:link', NS)
            )
        ]
        self.assertGreater(len(series_entries), 0)

    def test_author_detail_sub_feed_series_entry_has_book_count(self):
        """Series entry <content> contains a positive integer (book count)."""
        self.assertIsNotNone(self.author_with_series)
        response = self.client.get(f'{OPDS_BASE}authors/{self.author_with_series.pk}/series/')
        root = _parse(response)
        series_entries = [
            e for e in root.findall('atom:entry', NS)
            if any(
                f'{OPDS_BASE}series/' in lnk.get('href', '')
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

        response = self.client.get(f'{OPDS_BASE}authors/{author_all_series.pk}/series/')
        root = _parse(response)
        titles = _get_entry_titles(root)
        self.assertNotIn('Standalone Books', titles)

    def test_author_detail_sub_feed_series_has_standalone_entry_first(self):
        """For author_with_series the first entry is 'Standalone Books'."""
        self.assertIsNotNone(self.author_with_series)
        response = self.client.get(f'{OPDS_BASE}authors/{self.author_with_series.pk}/series/')
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        first_title = entries[0].findtext('atom:title', namespaces=NS)
        self.assertEqual(first_title, 'Standalone Books')

    def test_author_detail_sub_feed_series_standalone_entry_links_to_series_none(self):
        """'Standalone Books' entry links to opds:root/authors/<pk>/books/?series=none."""
        self.assertIsNotNone(self.author_with_series)
        response = self.client.get(f'{OPDS_BASE}authors/{self.author_with_series.pk}/series/')
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        standalone_entry = next(
            (e for e in entries if e.findtext('atom:title', namespaces=NS) == 'Standalone Books'),
            None,
        )
        self.assertIsNotNone(standalone_entry, 'Standalone Books entry not found')
        hrefs = [lnk.get('href', '') for lnk in standalone_entry.findall('atom:link', NS)]
        self.assertTrue(
            any(f'{OPDS_BASE}authors/{self.author_with_series.pk}/books/?series=none' in h for h in hrefs),
            msg=f'Expected ?series=none href in {hrefs}',
        )

    def test_author_detail_sub_feed_series_standalone_entry_has_count(self):
        """'Standalone Books' entry <content> contains the correct standalone book count."""
        self.assertIsNotNone(self.author_with_series)
        expected_count = self.author_with_series.books.filter(
            bookserieslink__isnull=True,
        ).count()
        self.assertGreater(expected_count, 0)

        response = self.client.get(f'{OPDS_BASE}authors/{self.author_with_series.pk}/series/')
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
        """GET opds:root/authors/<pk>/books/?series=none → only standalone books."""
        self.assertIsNotNone(self.author_with_series)
        expected = self.author_with_series.books.filter(
            bookserieslink__isnull=True,
        ).count()
        self.assertGreater(expected, 0)

        total = _count_all_pages(
            self.client,
            f'{OPDS_BASE}authors/{self.author_with_series.pk}/books/?series=none',
        )
        self.assertEqual(total, expected)

    # ------------------------------------------------------------------
    # Acquisition links
    # ------------------------------------------------------------------

    def test_author_books_acquisition_link_always_rendered(self):
        """GET opds:root/authors/<pk>/books/ → every entry has one acquisition link.

        The catalog is fully browsable for anonymous callers; download
        permission is enforced at the download endpoint, not in the feed.
        """
        response = self.client.get(f'{OPDS_BASE}authors/{self.any_author.pk}/books/')
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

        response = self.client.get(f'{OPDS_BASE}authors/{self.any_author.pk}/books/')
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
        response = self.client.get(f'{OPDS_BASE}authors/{self.any_author.pk}/books/')
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        for entry in entries:
            acq_link = next(
                lnk for lnk in entry.findall('atom:link', NS)
                if lnk.get('rel') == 'http://opds-spec.org/acquisition'
            )
            self.assertEqual(acq_link.get('type'), 'application/octet-stream')


# ---------------------------------------------------------------------------
# OPDSEntryImageTest
# ---------------------------------------------------------------------------

class OPDSEntryImageTest(OPDSThrottleResetMixin, TestCase):
    """Tests the §8 'logo for every non-book entry' rule.

    Every navigation entry must advertise the application logo as its
    thumbnail; book (acquisition) entries must not.
    """

    @classmethod
    def setUpTestData(cls):
        create_test_dataset()
        cls.author_with_books = Author.objects.filter(
            Exists(Book.objects.filter(authors=OuterRef('pk')))
        ).first()
        cls.author_with_series = (
            Author.objects
            .filter(Exists(Book.objects.filter(
                authors=OuterRef('pk'), bookserieslink__isnull=False,
            )))
            .first()
        )

    def _assert_all_entries_have_logo(self, root):
        entries = root.findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        for entry in entries:
            logo_links = [
                lnk for lnk in _links_by_rel(entry, THUMBNAIL_REL)
                if lnk.get('href', '').endswith(LOGO_HREF_SUFFIX)
            ]
            self.assertEqual(
                len(logo_links), 1,
                msg=f'Entry {entry.findtext("atom:title", namespaces=NS)!r} '
                    f'missing logo thumbnail',
            )
            self.assertEqual(logo_links[0].get('type'), 'image/png')

    def test_root_feed_entries_have_logo_thumbnail(self):
        """Every entry in opds:root carries the logo thumbnail link."""
        self._assert_all_entries_have_logo(_parse(self.client.get(OPDS_BASE)))

    def test_author_tree_entries_have_logo_thumbnail(self):
        """Every entry in opds:root/authors/tree/ carries the logo thumbnail."""
        self._assert_all_entries_have_logo(
            _parse(self.client.get(f'{OPDS_BASE}authors/tree/'))
        )

    def test_author_results_entries_have_logo_thumbnail(self):
        """Every entry in opds:root/authors/?filter=b carries the logo thumbnail."""
        self._assert_all_entries_have_logo(
            _parse(self.client.get(f'{OPDS_BASE}authors/?filter=b'))
        )

    def test_author_detail_entries_have_logo_thumbnail(self):
        """Every sub-feed entry in the author detail feed carries the logo."""
        self._assert_all_entries_have_logo(
            _parse(self.client.get(f'{OPDS_BASE}authors/{self.author_with_books.pk}/'))
        )

    def test_author_series_entries_have_logo_thumbnail(self):
        """Every entry in the author series feed carries the logo thumbnail."""
        self._assert_all_entries_have_logo(
            _parse(self.client.get(f'{OPDS_BASE}authors/{self.author_with_series.pk}/series/'))
        )

    def test_logo_thumbnail_href_is_absolute_url(self):
        """The logo thumbnail href is an absolute URL (starts with http)."""
        root = _parse(self.client.get(OPDS_BASE))
        entry = root.findall('atom:entry', NS)[0]
        logo = _links_by_rel(entry, THUMBNAIL_REL)[0]
        self.assertTrue(logo.get('href', '').startswith('http'))

    def test_book_entries_do_not_use_logo(self):
        """Book (acquisition) entries never carry the logo thumbnail link."""
        root = _parse(self.client.get(
            f'{OPDS_BASE}authors/{self.author_with_books.pk}/books/'
        ))
        entries = root.findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        for entry in entries:
            logo_links = [
                lnk for lnk in _links_by_rel(entry, THUMBNAIL_REL)
                if lnk.get('href', '').endswith(LOGO_HREF_SUFFIX)
            ]
            self.assertEqual(len(logo_links), 0)


# ---------------------------------------------------------------------------
# OPDSBookVerbosityTest
# ---------------------------------------------------------------------------

class OPDSBookVerbosityTest(OPDSThrottleResetMixin, TestCase):
    """Tests the §6.5a thin-default / ?detail=thick split on author book feeds.

    Also verifies the §6.5 complete book-entry shape (no Atom <author>,
    author/series rel="related" links, <calibre:series>, and sanitized
    <content type="xhtml">).
    """

    @classmethod
    def setUpTestData(cls):
        create_test_dataset()
        cls.any_author = Author.objects.filter(
            Exists(Book.objects.filter(authors=OuterRef('pk')))
        ).first()
        cls.author_with_series = (
            Author.objects
            .filter(Exists(Book.objects.filter(
                authors=OuterRef('pk'), bookserieslink__isnull=False,
            )))
            .first()
        )

        # A dedicated author + described book to exercise the xhtml content
        # path and the allowlist sanitizer (canonical books have no
        # description).
        cls.described_author = Author.objects.create(
            first_name='Verbo', last_name='Sity',
        )
        lang = Language.objects.first()
        cls.described_book = Book.objects.create(
            title='AAA Sanitized Sample',
            language=lang,
            description='<p>Keep <strong>this</strong>.</p>'
                        '<ul><li>one</li></ul>'
                        'line<br/>break<br>end'
                        '<script>alert(1)</script>'
                        '<iframe src="x"></iframe>',
        )
        cls.described_book.authors.add(cls.described_author)

        # Give the described author enough books to span >1 page so the
        # ?detail=thick pagination-propagation behaviour can be exercised
        # (canonical-dataset authors each have only a handful of books).
        extra = Book.objects.bulk_create([
            Book(title=f'Paginated Book {i:02d}', language=lang)
            for i in range(25)
        ])
        through = Book.authors.through
        through.objects.bulk_create([
            through(book_id=book.pk, author_id=cls.described_author.pk)
            for book in extra
        ])

    def _book_entries(self, root):
        return root.findall('atom:entry', NS)

    # ---- thin default ----

    def test_author_books_feed_thin_by_default(self):
        """Default author book entries are thin: no content/calibre/related."""
        root = _parse(self.client.get(f'{OPDS_BASE}authors/{self.any_author.pk}/books/'))
        entries = self._book_entries(root)
        self.assertGreater(len(entries), 0)
        for entry in entries:
            self.assertIsNone(entry.find('atom:content', NS))
            self.assertIsNone(entry.find('calibre:series', NS))
            self.assertEqual(len(_links_by_rel(entry, 'related')), 0)
            self.assertEqual(len(entry.findall('atom:author', NS)), 0)

    def test_thin_entry_has_mandatory_alternate_link(self):
        """Each thin entry has exactly one rel=alternate link to /books/<pk>/."""
        root = _parse(self.client.get(f'{OPDS_BASE}authors/{self.any_author.pk}/books/'))
        entries = self._book_entries(root)
        self.assertGreater(len(entries), 0)
        for entry in entries:
            alt = _links_by_rel(entry, 'alternate')
            self.assertEqual(len(alt), 1)
            self.assertEqual(
                alt[0].get('type'),
                'application/atom+xml;type=entry;profile=opds-catalog',
            )
            entry_id = entry.findtext('atom:id', namespaces=NS)
            pk = entry_id.split(':')[-1]
            self.assertTrue(alt[0].get('href', '').endswith(f'{OPDS_BASE}books/{pk}/'))

    def test_thin_entry_has_thumbnail_no_full_image(self):
        """A thin entry has a thumbnail link but no full-size image link."""
        root = _parse(self.client.get(f'{OPDS_BASE}authors/{self.any_author.pk}/books/'))
        entry = self._book_entries(root)[0]
        self.assertEqual(len(_links_by_rel(entry, THUMBNAIL_REL)), 1)
        self.assertEqual(len(_links_by_rel(entry, IMAGE_REL)), 0)

    def test_thin_pagination_links_have_no_detail_param(self):
        """Default (thin) feed pagination links carry no detail param."""
        root = _parse(self.client.get(
            f'{OPDS_BASE}authors/{self.described_author.pk}/books/'
        ))
        next_links = _get_link_hrefs(root, 'next')
        self.assertTrue(next_links, 'Expected a paginated feed with a next link')
        for rel in ('next', 'first'):
            for href in _get_link_hrefs(root, rel):
                self.assertNotIn('detail=', href)

    # ---- thick ----

    def test_author_books_feed_thick_has_author_related_links(self):
        """Thick entries carry author rel=related links and no Atom <author>."""
        root = _parse(self.client.get(
            f'{OPDS_BASE}authors/{self.any_author.pk}/books/?detail=thick'
        ))
        entries = self._book_entries(root)
        self.assertGreater(len(entries), 0)
        for entry in entries:
            related = _links_by_rel(entry, 'related')
            author_related = [
                lnk for lnk in related if f'{OPDS_BASE}authors/' in lnk.get('href', '')
            ]
            self.assertGreater(len(author_related), 0)
            self.assertEqual(len(entry.findall('atom:author', NS)), 0)

    def test_thick_entry_has_full_image_and_alternate(self):
        """Thick entries add the full-size image and keep the alternate link."""
        root = _parse(self.client.get(
            f'{OPDS_BASE}authors/{self.any_author.pk}/books/?detail=thick'
        ))
        entry = self._book_entries(root)[0]
        self.assertEqual(len(_links_by_rel(entry, IMAGE_REL)), 1)
        self.assertEqual(len(_links_by_rel(entry, 'alternate')), 1)

    def test_thick_param_propagates_to_pagination_links(self):
        """detail=thick is preserved on every first/next/previous link.

        Exercises page 1 (first + next) and page 2 (first + previous) so all
        three pagination rels are asserted; described_author has 26 books,
        which spans two pages at the default page size of 20.
        """
        base = f'{OPDS_BASE}authors/{self.described_author.pk}/books/?detail=thick'

        page_1 = _parse(self.client.get(base))
        self.assertTrue(
            _get_link_hrefs(page_1, 'next'),
            'Expected a paginated feed with a next link',
        )

        page_2 = _parse(self.client.get(base + '&page=2'))
        self.assertTrue(
            _get_link_hrefs(page_2, 'previous'),
            'Expected page 2 to carry a previous link',
        )

        seen_rels = set()
        for root in (page_1, page_2):
            for rel in ('first', 'next', 'previous'):
                for href in _get_link_hrefs(root, rel):
                    seen_rels.add(rel)
                    self.assertIn('detail=thick', href)

        self.assertEqual(seen_rels, {'first', 'next', 'previous'})

    def test_thick_series_book_has_calibre_and_series_related(self):
        """A series-linked book in thick mode has calibre:series + series related link."""
        root = _parse(self.client.get(
            f'{OPDS_BASE}authors/{self.author_with_series.pk}/books/?detail=thick'
        ))
        series_entries = [
            e for e in self._book_entries(root)
            if e.find('calibre:series', NS) is not None
        ]
        self.assertGreater(len(series_entries), 0)
        for entry in series_entries:
            self.assertIsNotNone(entry.find('calibre:series', NS))
            self.assertIsNotNone(entry.find('calibre:series_index', NS))
            series_related = [
                lnk for lnk in _links_by_rel(entry, 'related')
                if f'{OPDS_BASE}series/' in lnk.get('href', '')
            ]
            self.assertGreater(len(series_related), 0)

    def test_thick_entry_content_is_sanitized_xhtml(self):
        """A described book's thick content is xhtml with disallowed tags stripped."""
        root = _parse(self.client.get(
            f'{OPDS_BASE}authors/{self.described_author.pk}/books/?detail=thick'
        ))
        entry = next(
            e for e in self._book_entries(root)
            if e.findtext('atom:id', namespaces=NS).endswith(str(self.described_book.pk))
        )
        content = entry.find('atom:content', NS)
        self.assertIsNotNone(content)
        self.assertEqual(content.get('type'), 'xhtml')
        div = content.find('xhtml:div', NS)
        self.assertIsNotNone(div)
        # Allowlisted tags survive.
        self.assertIsNotNone(div.find('xhtml:p', NS))
        self.assertIsNotNone(div.find('.//xhtml:strong', NS))
        # Disallowed tags (script/iframe) are stripped, and script text dropped.
        rendered = ET.tostring(div, encoding='unicode')
        self.assertNotIn('script', rendered)
        self.assertNotIn('iframe', rendered)
        self.assertNotIn('alert(1)', rendered)


class OPDSThickPropagationTest(OPDSThrottleResetMixin, TestCase):
    """Tests the §6.5a Propagation rule for the sticky ``?detail=thick`` flag.

    ``detail=thick`` is a catalog-wide preference: because OPDS clients only
    follow links, it must be re-appended to every browsable-catalog link
    (subsection, search query-template, self/start, pagination, thick-entry
    related) and omitted from non-feed / always-complete links (alternate,
    acquisition, image/thumbnail, logo, OpenSearch description).
    """

    @classmethod
    def setUpTestData(cls):
        create_test_dataset()
        cls.any_author = Author.objects.filter(
            Exists(Book.objects.filter(authors=OuterRef('pk')))
        ).first()
        # An author with both a series-linked book and a standalone book so the
        # series feed renders both the per-series and "Standalone Books" links.
        cls.author_with_series_and_standalone = (
            Author.objects
            .filter(Exists(Book.objects.filter(
                authors=OuterRef('pk'), bookserieslink__isnull=False,
            )))
            .filter(Exists(Book.objects.filter(
                authors=OuterRef('pk'), bookserieslink__isnull=True,
            )))
            .first()
        )

    @staticmethod
    def _subsection_hrefs(root):
        """Return all entry-level rel=subsection hrefs in a feed."""
        return [
            lnk.get('href', '')
            for entry in root.findall('atom:entry', NS)
            for lnk in _links_by_rel(entry, 'subsection')
        ]

    # ---- Root feed ----

    def test_root_subsection_links_preserve_detail(self):
        """Every root subsection link carries detail=thick."""
        root = _parse(self.client.get(f'{OPDS_BASE}?detail=thick'))
        hrefs = self._subsection_hrefs(root)
        self.assertEqual(len(hrefs), 4)  # Authors, Genres, Series, Books
        for href in hrefs:
            self.assertIn('detail=thick', href)

    def test_root_search_query_link_preserves_detail(self):
        """The atom search-query link carries detail=thick; description does not."""
        root = _parse(self.client.get(f'{OPDS_BASE}?detail=thick'))
        search_entry = next(
            e for e in root.findall('atom:entry', NS)
            if e.findtext('atom:title', namespaces=NS) == 'Search'
        )
        query_link = next(
            lnk for lnk in _links_by_rel(search_entry, 'search')
            if lnk.get('type') == 'application/atom+xml'
        )
        description_link = next(
            lnk for lnk in _links_by_rel(search_entry, 'search')
            if lnk.get('type') == 'application/opensearchdescription+xml'
        )
        self.assertIn('detail=thick', query_link.get('href', ''))
        self.assertNotIn('detail=thick', description_link.get('href', ''))

    def test_root_self_and_start_links_preserve_detail(self):
        """The feed self and start links carry detail=thick."""
        root = _parse(self.client.get(f'{OPDS_BASE}?detail=thick'))
        for rel in ('self', 'start'):
            hrefs = _get_link_hrefs(root, rel)
            self.assertTrue(hrefs, f'Expected a {rel} link')
            for href in hrefs:
                self.assertIn('detail=thick', href)

    def test_root_logo_thumbnail_link_omits_detail(self):
        """The non-book logo thumbnail links never carry detail=thick."""
        root = _parse(self.client.get(f'{OPDS_BASE}?detail=thick'))
        logo_hrefs = [
            lnk.get('href', '')
            for entry in root.findall('atom:entry', NS)
            for lnk in _links_by_rel(entry, THUMBNAIL_REL)
        ]
        self.assertTrue(logo_hrefs, 'Expected logo thumbnail links')
        for href in logo_hrefs:
            self.assertNotIn('detail=', href)

    # ---- Author navigation feeds ----

    def test_author_tree_subsection_links_preserve_detail(self):
        """Every author-tree child and the synthetic "all" link carry detail=thick."""
        root = _parse(self.client.get(f'{OPDS_BASE}authors/tree/a/?detail=thick'))
        hrefs = self._subsection_hrefs(root)
        self.assertGreater(len(hrefs), 1)  # synthetic "all a" + children
        for href in hrefs:
            self.assertIn('detail=thick', href)

    def test_author_results_links_preserve_detail(self):
        """Author-result subsection and first/next pagination links carry detail=thick."""
        root = _parse(self.client.get(f'{OPDS_BASE}authors/?filter=b&detail=thick'))
        sub_hrefs = self._subsection_hrefs(root)
        self.assertTrue(sub_hrefs)
        for href in sub_hrefs:
            self.assertIn('detail=thick', href)
        for rel in ('first', 'next'):
            hrefs = _get_link_hrefs(root, rel)
            self.assertTrue(hrefs, f'Expected a {rel} pagination link')
            for href in hrefs:
                self.assertIn('detail=thick', href)

    def test_author_detail_subsection_links_preserve_detail(self):
        """All three author-detail subsection links carry detail=thick."""
        root = _parse(self.client.get(
            f'{OPDS_BASE}authors/{self.any_author.pk}/?detail=thick'
        ))
        hrefs = self._subsection_hrefs(root)
        self.assertEqual(len(hrefs), 3)  # Books by Title, New Arrivals, Books by Series
        for href in hrefs:
            self.assertIn('detail=thick', href)

    def test_author_series_links_preserve_detail(self):
        """Standalone and per-series subsection links carry detail=thick."""
        author = self.author_with_series_and_standalone
        self.assertIsNotNone(author, 'Dataset must yield a series+standalone author')
        root = _parse(self.client.get(
            f'{OPDS_BASE}authors/{author.pk}/series/?detail=thick'
        ))
        hrefs = self._subsection_hrefs(root)
        # At least the standalone link plus one per-series link.
        self.assertGreaterEqual(len(hrefs), 2)
        self.assertTrue(
            any('series=none' in href for href in hrefs),
            'Expected a Standalone Books link',
        )
        for href in hrefs:
            self.assertIn('detail=thick', href)

    # ---- Drill-down + default behaviour ----

    def test_detail_survives_drilldown_to_acquisition_feed(self):
        """Following the Books-by-Title link in thick mode reaches a thick feed."""
        detail = _parse(self.client.get(
            f'{OPDS_BASE}authors/{self.any_author.pk}/?detail=thick'
        ))
        books_entry = next(
            e for e in detail.findall('atom:entry', NS)
            if e.findtext('atom:title', namespaces=NS) == 'Books by Title'
        )
        books_href = _links_by_rel(books_entry, 'subsection')[0].get('href', '')
        self.assertIn('detail=thick', books_href)

        # Follow the link as a client would, using only the path + query.
        path = books_href.split(OPDS_BASE, 1)[1]
        acquisition = _parse(self.client.get(OPDS_BASE + path))
        entries = acquisition.findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        # Thick entries carry the full-size image link.
        for entry in entries:
            self.assertEqual(len(_links_by_rel(entry, IMAGE_REL)), 1)

    def test_navigation_links_omit_detail_by_default(self):
        """Without ?detail=thick no navigation link (feed- or entry-level) carries detail."""
        for url in (OPDS_BASE, f'{OPDS_BASE}authors/?filter=b'):
            root = _parse(self.client.get(url))
            # Feed-level links (self/start/pagination).
            for lnk in root.findall('atom:link', NS):
                self.assertNotIn('detail=', lnk.get('href', ''))
            # Every entry-level link (subsection, search-query, etc.).
            for entry in root.findall('atom:entry', NS):
                for lnk in entry.findall('atom:link', NS):
                    self.assertNotIn('detail=', lnk.get('href', ''))


# ---------------------------------------------------------------------------
# OPDSBookDetailTest
# ---------------------------------------------------------------------------

RELATED_REL = 'related'


def _make_cover_file(name='cover.jpg'):
    """Return a small in-memory JPEG ContentFile usable as a Book cover."""
    buffer = io.BytesIO()
    Image.new('RGB', (60, 90), color='red').save(buffer, format='JPEG')
    buffer.seek(0)
    return ContentFile(buffer.read(), name=name)


class OPDSBookDetailTest(OPDSThrottleResetMixin, BaseTestCase):
    """Tests for GET opds:root/books/<pk>/ — the complete book-detail feed.

    Uses ``BaseTestCase`` so ``book_1`` can carry a real cover image (the
    ``cover_opds_thumbnail``/``cover`` ImageSpecFields generate against a temp
    media root).  Per the catalog-is-fully-browsable convention the acquisition
    link is always rendered, so there are no permission-gating cases here.
    """

    @classmethod
    def setUpTestData(cls):
        cls.lang_en = Language.objects.create(code='en', name='English')

        cls.author_a = Author.objects.create(first_name='Isaac', last_name='Asimov')
        cls.author_b = Author.objects.create(first_name='Ray', last_name='Bradbury')

        # Padded name verifies the renderer/serializer .strip() behaviour.
        cls.series_1 = BookSeries.objects.create(name=' Foundation ')
        cls.series_2 = BookSeries.objects.create(name='Robot Series', parent=cls.series_1)

        cls.book_1 = Book.objects.create(
            title='Foundation',
            language=cls.lang_en,
            file_type='epub',
            description=(
                '<p>Foundation is a <strong>great</strong> novel.</p>'
                '<script>alert(1)</script>'
            ),
        )
        cls.book_1.authors.add(cls.author_a)
        cls.book_1.cover.save('cover.jpg', _make_cover_file())
        BookSeriesLink.objects.create(
            book=cls.book_1, series=cls.series_1, sequence_number=1,
        )

        # No cover — exercises the no_cover placeholder fallback.
        cls.book_2 = Book.objects.create(title='I, Robot', language=cls.lang_en)
        cls.book_2.authors.add(cls.author_a)
        BookSeriesLink.objects.create(
            book=cls.book_2, series=cls.series_1, sequence_number=2,
        )

        # No series — exercises the standalone (no calibre:series) path.
        cls.book_3 = Book.objects.create(title='Fahrenheit 451', language=cls.lang_en)
        cls.book_3.authors.add(cls.author_b)

    # -- helpers --------------------------------------------------------

    def _entry(self, book):
        """GET the book-detail feed for *book* and return its single <entry>."""
        root = _parse(self.client.get(f'{OPDS_BASE}books/{book.pk}/'))
        entries = root.findall('atom:entry', NS)
        self.assertEqual(len(entries), 1, 'Detail feed must hold exactly one entry')
        return entries[0]

    @staticmethod
    def _related_by_prefix(entry, path_fragment):
        """Return rel=related links whose href contains *path_fragment*."""
        return [
            lnk for lnk in _links_by_rel(entry, RELATED_REL)
            if path_fragment in lnk.get('href', '')
        ]

    # -- status / basics ------------------------------------------------

    def test_book_detail_status_200(self):
        """GET opds:root/books/<pk>/ → 200."""
        response = self.client.get(f'{OPDS_BASE}books/{self.book_1.pk}/')
        self.assertEqual(response.status_code, 200)

    def test_book_detail_404(self):
        """GET opds:root/books/99999/ → 404."""
        response = self.client.get(f'{OPDS_BASE}books/99999/')
        self.assertEqual(response.status_code, 404)

    def test_book_detail_is_acquisition_feed(self):
        """Book-detail Content-Type contains kind=acquisition."""
        response = self.client.get(f'{OPDS_BASE}books/{self.book_1.pk}/')
        self.assertIn('kind=acquisition', response['Content-Type'])

    def test_book_detail_has_title(self):
        """Entry <title> equals the book title."""
        self.assertEqual(self._entry(self.book_1).findtext('atom:title', namespaces=NS), 'Foundation')

    # -- authors --------------------------------------------------------

    def test_book_detail_has_author_related_link(self):
        """Entry has a rel=related link to the author detail with the right title/type."""
        entry = self._entry(self.book_1)
        author_links = self._related_by_prefix(entry, f'{OPDS_BASE}authors/{self.author_a.pk}/')
        self.assertEqual(len(author_links), 1)
        link = author_links[0]
        self.assertIn('kind=navigation', link.get('type', ''))
        self.assertEqual(link.get('title'), self.author_a.full_name)

    def test_book_detail_one_related_link_per_author(self):
        """A two-author book renders exactly two author rel=related links."""
        self.book_1.authors.add(self.author_b)
        entry = self._entry(self.book_1)
        for author in (self.author_a, self.author_b):
            self.assertEqual(
                len(self._related_by_prefix(entry, f'{OPDS_BASE}authors/{author.pk}/')), 1,
            )

    def test_book_detail_author_related_link_mandatory(self):
        """Every complete book entry has at least one author rel=related link."""
        entry = self._entry(self.book_3)
        self.assertGreaterEqual(len(self._related_by_prefix(entry, f'{OPDS_BASE}authors/')), 1)

    def test_book_detail_has_no_atom_author_element(self):
        """The entry emits no <author> Atom element — authors are rel=related only."""
        self.assertEqual(len(self._entry(self.book_1).findall('atom:author', NS)), 0)

    # -- content / description ------------------------------------------

    def test_book_detail_content_is_xhtml_type(self):
        """Entry has <content type="xhtml"> with a <div>; there is no <summary>."""
        entry = self._entry(self.book_1)
        content = entry.find('atom:content', NS)
        self.assertIsNotNone(content)
        self.assertEqual(content.get('type'), 'xhtml')
        self.assertIsNotNone(content.find('xhtml:div', NS))
        self.assertIsNone(entry.find('atom:summary', NS))

    def test_book_detail_content_has_description(self):
        """The <content> <div> text carries the book description text."""
        div = self._entry(self.book_1).find('atom:content/xhtml:div', NS)
        text = ''.join(div.itertext())
        self.assertIn('Foundation is a', text)
        self.assertIn('great', text)

    def test_book_detail_content_has_no_series_text(self):
        """The <content> contains no series text (series live in calibre:*/related)."""
        div = self._entry(self.book_1).find('atom:content/xhtml:div', NS)
        text = ''.join(div.itertext())
        self.assertNotIn('Foundation #1', text)
        self.assertNotIn('Belongs to series', text)

    def test_book_detail_content_sanitizes_disallowed_html(self):
        """Disallowed tags are stripped; allowlisted tags survive."""
        div = self._entry(self.book_1).find('atom:content/xhtml:div', NS)
        rendered = ET.tostring(div, encoding='unicode')
        self.assertIsNotNone(div.find('xhtml:p', NS))
        self.assertIsNotNone(div.find('.//xhtml:strong', NS))
        self.assertNotIn('script', rendered)
        self.assertNotIn('alert(1)', rendered)

    def test_book_detail_no_content_when_no_description(self):
        """A book with an empty description has no <content> element."""
        self.assertIsNone(self._entry(self.book_3).find('atom:content', NS))

    # -- calibre series -------------------------------------------------

    def test_book_detail_has_calibre_series(self):
        """Entry has <calibre:series>Foundation and <calibre:series_index>1."""
        entry = self._entry(self.book_1)
        self.assertEqual(entry.findtext('calibre:series', namespaces=NS), 'Foundation')
        self.assertEqual(entry.findtext('calibre:series_index', namespaces=NS), '1')

    def test_book_detail_calibre_series_name_stripped(self):
        """The <calibre:series> text has no leading/trailing whitespace."""
        text = self._entry(self.book_1).findtext('calibre:series', namespaces=NS)
        self.assertEqual(text, text.strip())

    def test_book_detail_one_calibre_series_pair_per_series(self):
        """A book in two series yields exactly two calibre:series pairs."""
        BookSeriesLink.objects.create(
            book=self.book_1, series=self.series_2, sequence_number=1,
        )
        entry = self._entry(self.book_1)
        self.assertEqual(len(entry.findall('calibre:series', NS)), 2)
        self.assertEqual(len(entry.findall('calibre:series_index', NS)), 2)

    def test_book_detail_no_calibre_series_when_standalone(self):
        """A standalone book has no calibre:series and no series rel=related link."""
        entry = self._entry(self.book_3)
        self.assertIsNone(entry.find('calibre:series', NS))
        self.assertEqual(len(self._related_by_prefix(entry, f'{OPDS_BASE}series/')), 0)

    # -- cover / thumbnail ----------------------------------------------

    def test_book_detail_cover_link_is_absolute_url(self):
        """The full-size cover link href is an absolute URL."""
        links = _links_by_rel(self._entry(self.book_1), IMAGE_REL)
        self.assertEqual(len(links), 1)
        self.assertTrue(links[0].get('href', '').startswith('http'))

    def test_book_detail_has_thumbnail_link(self):
        """The entry carries a cover thumbnail link."""
        self.assertEqual(len(_links_by_rel(self._entry(self.book_1), THUMBNAIL_REL)), 1)

    def test_book_detail_no_cover_uses_no_cover_fallback(self):
        """A cover-less book falls back to the no_cover placeholders (links never omitted)."""
        entry = self._entry(self.book_2)
        full = _links_by_rel(entry, IMAGE_REL)
        thumb = _links_by_rel(entry, THUMBNAIL_REL)
        self.assertEqual(len(full), 1)
        self.assertEqual(len(thumb), 1)
        self.assertTrue(full[0].get('href', '').endswith('/static/img/no_cover%20600x900.jpeg'))
        self.assertTrue(thumb[0].get('href', '').endswith('/static/img/no_cover%2040x60.jpeg'))

    # -- series related link --------------------------------------------

    def test_book_detail_has_series_related_link(self):
        """Entry has a rel=related link to the series, titled with the series name only."""
        entry = self._entry(self.book_1)
        series_links = self._related_by_prefix(entry, f'{OPDS_BASE}series/{self.series_1.pk}/')
        self.assertEqual(len(series_links), 1)
        self.assertEqual(series_links[0].get('title'), 'Foundation')

    def test_book_detail_author_and_series_related_links_distinguishable(self):
        """Author related links target /authors/<pk>/; series links target /series/<pk>/."""
        entry = self._entry(self.book_1)
        self.assertGreaterEqual(len(self._related_by_prefix(entry, f'{OPDS_BASE}authors/')), 1)
        self.assertGreaterEqual(len(self._related_by_prefix(entry, f'{OPDS_BASE}series/')), 1)

    # -- acquisition / alternate ----------------------------------------

    def test_book_detail_acquisition_link_always_rendered(self):
        """The acquisition link is always present (fully browsable catalog)."""
        entry = self._entry(self.book_1)
        acq = _links_by_rel(entry, ACQUISITION_REL)
        self.assertEqual(len(acq), 1)
        self.assertTrue(acq[0].get('href', '').endswith(f'{OPDS_BASE}books/{self.book_1.pk}/download/'))

    def test_book_detail_has_no_alternate_link(self):
        """The detail feed is the alternate target, so it carries no alternate link."""
        self.assertEqual(len(_links_by_rel(self._entry(self.book_1), 'alternate')), 0)
