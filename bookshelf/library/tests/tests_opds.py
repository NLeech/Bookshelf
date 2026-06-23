"""
OPDS v1.2 catalog tests.
"""
import base64
import io
import xml.etree.ElementTree as ET
import zipfile
from urllib.parse import quote

import pyzipper
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.db.models import Count, Exists, OuterRef
from django.test import TestCase
from parameterized import parameterized
from PIL import Image

from bookshelf.tests.base_test import BaseTestCase
from library.models import Author, Book, BookSeries, BookSeriesLink, Genre, Language
from library.tests.epub_test_utils import create_epub_one_author
from library.tests.fb2_test_utils import create_fb2_one_author
from library.tests.test_data_factory import create_test_dataset

User = get_user_model()


def _basic(username, password):
    """Return an HTTP Basic ``Authorization`` header value for *username*."""
    token = base64.b64encode(f'{username}:{password}'.encode()).decode()
    return f'Basic {token}'


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
ACQUISITION_REL = 'http://opds-spec.org/acquisition/open-access'


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
    # 3. Catalog entries — anonymous sees 5 (incl. Login), authed sees 4
    # ------------------------------------------------------------------

    def test_root_feed_anonymous_has_login_entry(self):
        """Anonymous root feed has 5 entries; Login subsection → /opds/v1/login/."""
        _, root = self._get_root()
        entries = root.findall('atom:entry', NS)
        self.assertEqual(len(entries), 5)

        titles = {e.findtext('atom:title', namespaces=NS) for e in entries}
        self.assertIn('Login', titles)

        login_entry = next(
            e for e in entries
            if e.findtext('atom:title', namespaces=NS) == 'Login'
        )
        subsection = _links_by_rel(login_entry, 'subsection')
        self.assertEqual(len(subsection), 1)
        self.assertTrue(
            subsection[0].get('href', '').endswith(f'{OPDS_BASE}login/'),
            msg=subsection[0].get('href', ''),
        )

    def test_root_feed_authenticated_omits_login_entry(self):
        """Authenticated root feed (valid Basic creds) has 4 entries; no Login."""
        User.objects.create_user(username='reader', email='reader@example.com', password='pass')
        response = self.client.get(
            self.ROOT_URL, HTTP_AUTHORIZATION=_basic('reader', 'pass')
        )
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        self.assertEqual(len(entries), 4)

        titles = {e.findtext('atom:title', namespaces=NS) for e in entries}
        self.assertNotIn('Login', titles)

    # ------------------------------------------------------------------
    # 4. Entry titles
    # ------------------------------------------------------------------

    def test_root_feed_entry_titles(self):
        _, root = self._get_root()
        entries = root.findall('atom:entry', NS)
        titles = {e.findtext('atom:title', namespaces=NS) for e in entries}
        self.assertEqual(titles, {'Authors', 'Genres', 'Series', 'Books', 'Login'})

    # ------------------------------------------------------------------
    # 5./6. Self and start links
    # ------------------------------------------------------------------

    @parameterized.expand(['self', 'start'])
    def test_root_feed_navigation_link(self, rel):
        """Feed has exactly one <link rel="self"|"start"> ending with opds:root/."""
        _, root = self._get_root()
        links = [lnk for lnk in root.findall('atom:link', NS) if lnk.get('rel') == rel]
        self.assertEqual(len(links), 1, f'Expected exactly one <link rel="{rel}">')
        href = links[0].get('href', '')
        self.assertTrue(
            href.endswith(OPDS_BASE),
            msg=f'{rel} link href {href!r} does not end with {OPDS_BASE}',
        )

    # ------------------------------------------------------------------
    # 7. Search is advertised via a feed-level OpenSearch link
    # ------------------------------------------------------------------

    def test_root_feed_search_link_at_feed_level(self):
        """Exactly one feed-level <link rel="search"> OpenSearch link exists,
        and there is no longer a 'Search' navigation <entry>."""
        _, root = self._get_root()

        feed_search_links = [
            lnk for lnk in root.findall('atom:link', NS)
            if lnk.get('rel') == 'search'
            and lnk.get('type') == 'application/opensearchdescription+xml'
        ]
        self.assertEqual(
            len(feed_search_links), 1,
            'Root feed must have exactly one feed-level '
            '<link rel="search" type="application/opensearchdescription+xml">',
        )
        self.assertTrue(
            feed_search_links[0].get('href', '').endswith('search/description.xml')
            or 'search/description.xml' in feed_search_links[0].get('href', ''),
            msg=feed_search_links[0].get('href', ''),
        )

        # The Search navigation entry must be gone.
        titles = {
            e.findtext('atom:title', namespaces=NS)
            for e in root.findall('atom:entry', NS)
        }
        self.assertNotIn('Search', titles)
        ids = {
            e.findtext('atom:id', namespaces=NS)
            for e in root.findall('atom:entry', NS)
        }
        self.assertNotIn('tag:bookshelf:search', ids)

    def test_root_feed_has_templated_atom_search_link(self):
        """A feed-level templated rel="search" type="application/atom+xml"
        link carrying {searchTerms} is advertised (mirrors Flibusta).  Readers
        synthesize an inline "Search" catalog entry from it."""
        _, root = self._get_root()
        atom_search_links = [
            lnk for lnk in root.findall('atom:link', NS)
            if lnk.get('rel') == 'search'
            and lnk.get('type') == 'application/atom+xml'
        ]
        self.assertEqual(
            len(atom_search_links), 1,
            'Root feed must emit exactly one templated atom+xml '
            'rel="search" link',
        )
        self.assertIn('{searchTerms}', atom_search_links[0].get('href', ''))
        self.assertIn('search/?q=', atom_search_links[0].get('href', ''))

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

    @parameterized.expand([
        ('A', '137'),  # A=137 authors
        ('B', '58'),   # B=58 authors
    ])
    def test_author_alphabet_root_has_letter_entry(self, letter, count):
        """GET opds:root/authors/tree/ → feed contains entry for letter with its count."""
        response = self.client.get(f'{OPDS_BASE}authors/tree/')
        self.assertEqual(response.status_code, 200)
        entries = _parse(response).findall('atom:entry', NS)
        titles = [e.findtext('atom:title', namespaces=NS) for e in entries]
        self.assertIn(letter, titles)
        entry = next(e for e in entries if e.findtext('atom:title', namespaces=NS) == letter)
        self.assertIn(count, entry.findtext('atom:content', namespaces=NS))

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

    @parameterized.expand([
        ('list', 'authors/?filter=b'),  # flat author list
        ('tree', 'authors/tree/'),       # alphabet tree root
    ])
    def test_author_feed_is_navigation(self, _name, path):
        """Flat list and tree root Content-Type both contain kind=navigation."""
        response = self.client.get(f'{OPDS_BASE}{path}')
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
        """GET opds:root/authors/tree/a/ → first entry is 'all A'."""
        response = self.client.get(f'{OPDS_BASE}authors/tree/a/')
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        first_title = entries[0].findtext('atom:title', namespaces=NS)
        self.assertEqual(first_title, 'all A')

    def test_author_tree_sub_node_all_entry_links_to_filter(self):
        """'all A' entry in opds:root/authors/tree/a/ links to ?filter=a."""
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

    @parameterized.expand([
        ('books_alpha', 'books/'),     # opds:root/authors/<pk>/books/
        ('books_recent', 'books/recent/'),  # opds:root/authors/<pk>/books/recent/
        ('series', 'series/'),          # opds:root/authors/<pk>/series/
    ])
    def test_author_detail_sub_feed_status_200(self, _name, suffix):
        """GET each author sub-feed endpoint → HTTP 200."""
        response = self.client.get(f'{OPDS_BASE}authors/{self.any_author.pk}/{suffix}')
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

    def test_author_detail_sub_feed_series_is_navigation(self):
        """Author series feed Content-Type contains kind=navigation."""
        response = self.client.get(f'{OPDS_BASE}authors/{self.any_author.pk}/series/')
        self.assertIn('kind=navigation', response['Content-Type'])

    def _author_series_entries(self, root, author):
        """Return the per-series entries (author-scoped ?series=<pk> links).

        A series entry links to ``authors/<pk>/books/?series=<digit>``; the
        "Standalone Books" entry (``?series=none``) is excluded.
        """
        prefix = f'{OPDS_BASE}authors/{author.pk}/books/?series='
        return [
            e for e in root.findall('atom:entry', NS)
            if any(
                prefix in lnk.get('href', '')
                and 'series=none' not in lnk.get('href', '')
                for lnk in e.findall('atom:link', NS)
            )
        ]

    def test_author_detail_sub_feed_series_has_series(self):
        """For author_with_series: series feed has at least one author-scoped series entry."""
        self.assertIsNotNone(
            self.author_with_series,
            'Canonical dataset should contain an author with series books',
        )
        response = self.client.get(f'{OPDS_BASE}authors/{self.author_with_series.pk}/series/')
        root = _parse(response)
        series_entries = self._author_series_entries(root, self.author_with_series)
        self.assertGreater(len(series_entries), 0)

    def test_author_detail_sub_feed_series_entry_has_book_count(self):
        """Series entry <content> contains a positive integer (book count)."""
        self.assertIsNotNone(self.author_with_series)
        response = self.client.get(f'{OPDS_BASE}authors/{self.author_with_series.pk}/series/')
        root = _parse(response)
        series_entries = self._author_series_entries(root, self.author_with_series)
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
                if lnk.get('rel') == ACQUISITION_REL
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
                else 'application/fb2+zip'
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
                if lnk.get('rel') == ACQUISITION_REL
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
                if lnk.get('rel') == ACQUISITION_REL
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

    @parameterized.expand([
        ('root', lambda self: OPDS_BASE),
        ('author_tree', lambda self: f'{OPDS_BASE}authors/tree/'),
        ('author_results', lambda self: f'{OPDS_BASE}authors/?filter=b'),
        ('author_detail', lambda self: f'{OPDS_BASE}authors/{self.author_with_books.pk}/'),
        ('author_series', lambda self: f'{OPDS_BASE}authors/{self.author_with_series.pk}/series/'),
    ])
    def test_entries_have_logo_thumbnail(self, _name, url_fn):
        """Every entry in each navigation feed carries the logo thumbnail link."""
        self._assert_all_entries_have_logo(_parse(self.client.get(url_fn(self))))

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


# ---------------------------------------------------------------------------
# OPDSBookListFeedTest
# ---------------------------------------------------------------------------

class OPDSBookListFeedTest(OPDSThrottleResetMixin, TestCase):
    """Tests for the book alphabet-tree and flat results endpoints.

    Covers the three book browse endpoints:
    - ``opds:root/books/`` — flat, paginated acquisition results
    - ``opds:root/books/tree/`` — alphabet tree root (navigation)
    - ``opds:root/books/tree/<name>/`` — alphabet sub-tree (navigation)

    Fixture: canonical dataset (560 books: A=222, B=167, M=43, П=83,
    0-9=14, Other=31; no book starts with Z).
    """

    @classmethod
    def setUpTestData(cls):
        create_test_dataset()

    # ------------------------------------------------------------------
    # Tree root
    # ------------------------------------------------------------------

    @parameterized.expand([
        ('root', 'books/tree/'),       # alphabet tree root
        ('sub_node', 'books/tree/a/'),  # A=222 is expandable
    ])
    def test_book_tree_status_200(self, _name, path):
        """GET opds:root/books/tree/ and an expandable sub-node → HTTP 200."""
        response = self.client.get(f'{OPDS_BASE}{path}')
        self.assertEqual(response.status_code, 200)

    def test_book_tree_is_navigation_feed(self):
        """GET opds:root/books/tree/ → Content-Type contains kind=navigation."""
        response = self.client.get(f'{OPDS_BASE}books/tree/')
        self.assertIn('kind=navigation', response['Content-Type'])

    def test_book_alphabet_root_has_a_entry(self):
        """GET opds:root/books/tree/ → entry for 'A' with count 222."""
        response = self.client.get(f'{OPDS_BASE}books/tree/')
        root = _parse(response)
        entries = root.findall('atom:entry', NS)
        a_entry = next(
            (e for e in entries if e.findtext('atom:title', namespaces=NS) == 'A'),
            None,
        )
        self.assertIsNotNone(a_entry, 'Expected an "A" root entry')
        self.assertIn('222', a_entry.findtext('atom:content', namespaces=NS))

    def test_book_alphabet_root_no_entry_for_missing_letter(self):
        """GET opds:root/books/tree/ → no 'Z'/'z' root entry (no Z books)."""
        response = self.client.get(f'{OPDS_BASE}books/tree/')
        titles = _get_entry_titles(_parse(response))
        self.assertNotIn('Z', titles)
        self.assertNotIn('z', titles)

    def test_book_tree_entries_have_count_in_content(self):
        """Every opds:root/books/tree/ entry carries its item count in content."""
        response = self.client.get(f'{OPDS_BASE}books/tree/')
        entries = _parse(response).findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        for entry in entries:
            content = entry.findtext('atom:content', namespaces=NS) or ''
            self.assertRegex(content, r'\d+', f'Entry content {content!r} has no count')

    # ------------------------------------------------------------------
    # Tree sub-nodes
    # ------------------------------------------------------------------

    def test_book_a_is_expanded_subtree(self):
        """GET opds:root/books/tree/a/ → nav sub-entries, not a flat list of 222."""
        response = self.client.get(f'{OPDS_BASE}books/tree/a/')
        titles = set(_get_entry_titles(_parse(response)))
        self.assertEqual(titles, {'all A', 'Al', 'An', 'Ar'})

    def test_book_tree_al_sub_entries(self):
        """GET opds:root/books/tree/al/ → entries Ali, All, all Al — no others."""
        response = self.client.get(f'{OPDS_BASE}books/tree/al/')
        titles = set(_get_entry_titles(_parse(response)))
        self.assertEqual(titles, {'all Al', 'Ali', 'All'})

    @parameterized.expand([
        ('leaf_node', 'm'),       # M=43 ≤ 50 is a leaf, never addressed by path
        ('nonexistent_node', 'z'),  # no Z node at all
    ])
    def test_book_tree_node_returns_404(self, _name, segment):
        """GET opds:root/books/tree/<leaf|missing>/ → HTTP 404."""
        response = self.client.get(f'{OPDS_BASE}books/tree/{segment}/')
        self.assertEqual(response.status_code, 404)

    def test_book_tree_sub_node_has_all_entry_first(self):
        """GET opds:root/books/tree/a/ → first entry is 'all A' with count 222."""
        response = self.client.get(f'{OPDS_BASE}books/tree/a/')
        entries = _parse(response).findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        self.assertEqual(entries[0].findtext('atom:title', namespaces=NS), 'all A')
        self.assertIn('222', entries[0].findtext('atom:content', namespaces=NS))

    def test_book_tree_sub_node_all_entry_links_to_filter(self):
        """The 'all A' entry in opds:root/books/tree/a/ links to ?filter=a."""
        response = self.client.get(f'{OPDS_BASE}books/tree/a/')
        all_entry = _parse(response).findall('atom:entry', NS)[0]
        hrefs = _get_link_hrefs(all_entry, 'subsection')
        self.assertTrue(
            any(h.endswith(f'{OPDS_BASE}books/?filter=a') for h in hrefs),
            msg=f'Expected books/?filter=a in {hrefs}',
        )

    @parameterized.expand([
        # Leaf child links to the flat ?filter= results.
        ('leaf_filter', 'Ar', 'books/?filter=ar'),
        # Expandable child links to its own sub-tree.
        ('expandable_subtree', 'Al', 'books/tree/al/'),
    ])
    def test_book_tree_child_links_to(self, _name, child_title, href_suffix):
        """Each child in opds:root/books/tree/a/ links to its proper target."""
        response = self.client.get(f'{OPDS_BASE}books/tree/a/')
        entries = _parse(response).findall('atom:entry', NS)
        child = next(
            e for e in entries
            if e.findtext('atom:title', namespaces=NS) == child_title
        )
        hrefs = _get_link_hrefs(child, 'subsection')
        self.assertTrue(
            any(h.endswith(f'{OPDS_BASE}{href_suffix}') for h in hrefs),
            msg=f'Expected {href_suffix} in {hrefs}',
        )

    @parameterized.expand([
        # (filter prefix, expected query value) — non-ASCII prefixes must be
        # percent-encoded so readers re-request the next/prev page with the
        # same encoding instead of double-encoding it into a 404.
        ('ascii', 'a', 'a'),
        ('cyrillic', 'а', quote('а', safe='')),
    ])
    def test_leaf_results_href_percent_encodes_filter(self, _name, prefix, expected):
        """A leaf node's ?filter= href percent-encodes non-ASCII prefixes."""
        from library.opds.serializers import _leaf_results_href
        from library.services import AlphabetTree

        node = AlphabetTree(name=prefix, filter=prefix)
        href = _leaf_results_href(node, 'http://x/opds/v1/', 'books')
        self.assertEqual(href, f'http://x/opds/v1/books/?filter={expected}')

    def test_book_tree_root_has_other_entry_linking_to_subtree(self):
        """GET opds:root/books/tree/ → 'Other' entry (count 31) links to tree/other/."""
        response = self.client.get(f'{OPDS_BASE}books/tree/')
        entries = _parse(response).findall('atom:entry', NS)
        other = next(
            (e for e in entries if e.findtext('atom:title', namespaces=NS) == 'Other'),
            None,
        )
        self.assertIsNotNone(other, 'Expected an "Other" root entry')
        self.assertIn('31', other.findtext('atom:content', namespaces=NS))
        hrefs = _get_link_hrefs(other, 'subsection')
        self.assertTrue(
            any(h.endswith(f'{OPDS_BASE}books/tree/other/') for h in hrefs),
            msg=f'Expected books/tree/other/ in {hrefs}',
        )

    def test_book_tree_other_subtree_all_entry_uses_regex(self):
        """GET opds:root/books/tree/other/ → first entry 'all Other' links via ?regex=."""
        response = self.client.get(f'{OPDS_BASE}books/tree/other/')
        self.assertEqual(response.status_code, 200)
        entries = _parse(response).findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        self.assertEqual(entries[0].findtext('atom:title', namespaces=NS), 'all Other')
        self.assertIn('31', entries[0].findtext('atom:content', namespaces=NS))
        hrefs = _get_link_hrefs(entries[0], 'subsection')
        self.assertTrue(
            any(f'{OPDS_BASE}books/?regex=' in h for h in hrefs),
            msg=f'Expected a books/?regex= results link in {hrefs}',
        )

    def test_book_tree_entries_have_logo_thumbnail(self):
        """Every opds:root/books/tree/ entry carries the logo thumbnail link."""
        response = self.client.get(f'{OPDS_BASE}books/tree/')
        entries = _parse(response).findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        for entry in entries:
            hrefs = _get_link_hrefs(entry, THUMBNAIL_REL)
            self.assertTrue(
                any(h.endswith(LOGO_HREF_SUFFIX) for h in hrefs),
                msg=f'Entry missing logo thumbnail: {hrefs}',
            )

    # ------------------------------------------------------------------
    # Flat results
    # ------------------------------------------------------------------

    def test_book_results_is_acquisition_feed(self):
        """GET opds:root/books/?filter=m → Content-Type contains kind=acquisition."""
        response = self.client.get(f'{OPDS_BASE}books/?filter=m')
        self.assertIn('kind=acquisition', response['Content-Type'])

    def test_book_results_by_filter_status_200(self):
        """GET opds:root/books/?filter=m → HTTP 200 (M=43, leaf)."""
        response = self.client.get(f'{OPDS_BASE}books/?filter=m')
        self.assertEqual(response.status_code, 200)

    def test_book_results_has_correct_count(self):
        """GET opds:root/books/?filter=m → 20 entries (page 1 of 43)."""
        response = self.client.get(f'{OPDS_BASE}books/?filter=m')
        entries = _parse(response).findall('atom:entry', NS)
        self.assertEqual(len(entries), 20)

    @parameterized.expand([
        # filter= matches a title prefix.
        ('filter_m', 'books/?filter=m', 43),
        # Cyrillic filter, percent-encoded exactly as a real OPDS client sends it.
        ('cyrillic_filter', 'books/?filter=' + quote('п'), 83),
        # regex= matches via a full regular expression.
        ('digits_regex', 'books/?regex=^[0-9]', 14),
        # regex= takes precedence over filter= when both are present.
        ('regex_beats_filter', 'books/?filter=0-9&regex=^[0-9]', 14),
    ])
    def test_book_results_count_across_pages(self, _name, path, expected):
        """GET opds:root/books/ with filter/regex → expected total across pages."""
        total = _count_all_pages(self.client, f'{OPDS_BASE}{path}')
        self.assertEqual(total, expected)

    def test_book_results_excludes_other_letter(self):
        """GET opds:root/books/?filter=m → no title starting with 'B'."""
        response = self.client.get(f'{OPDS_BASE}books/?filter=m')
        titles = _get_entry_titles(_parse(response))
        self.assertTrue(titles)
        for title in titles:
            self.assertFalse(
                title.lower().startswith('b'),
                msg=f'Unexpected non-M title {title!r} in filter=m results',
            )

    def test_book_results_sorted_by_title(self):
        """Entries in opds:root/books/?filter=m are ordered by title ascending."""
        response = self.client.get(f'{OPDS_BASE}books/?filter=m')
        titles = _get_entry_titles(_parse(response))
        self.assertEqual(titles, sorted(titles, key=str.lower))

    def test_book_results_empty_filter_returns_empty_feed(self):
        """GET opds:root/books/?filter=z → HTTP 200 with zero entries."""
        response = self.client.get(f'{OPDS_BASE}books/?filter=z')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(_parse(response).findall('atom:entry', NS)), 0)

    def test_book_results_full_set_no_filter_paginated(self):
        """GET opds:root/books/ (no params) → 200 with a full first page of 20."""
        response = self.client.get(f'{OPDS_BASE}books/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(_parse(response).findall('atom:entry', NS)), 20)

    def test_book_results_entry_links_to_book_detail(self):
        """Each thin entry's rel=alternate link points to opds:root/books/<pk>/."""
        response = self.client.get(f'{OPDS_BASE}books/?filter=m')
        entries = _parse(response).findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        for entry in entries:
            entry_id = entry.findtext('atom:id', namespaces=NS) or ''
            pk = entry_id.split(':')[-1]
            alt = _links_by_rel(entry, 'alternate')
            self.assertEqual(len(alt), 1)
            self.assertTrue(alt[0].get('href', '').endswith(f'{OPDS_BASE}books/{pk}/'))

    def test_book_results_acquisition_link_always_rendered(self):
        """Every opds:root/books/ entry exposes exactly one acquisition link."""
        response = self.client.get(f'{OPDS_BASE}books/?filter=m')
        entries = _parse(response).findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        for entry in entries:
            self.assertEqual(len(_links_by_rel(entry, ACQUISITION_REL)), 1)

    def test_book_results_entries_thin_by_default(self):
        """GET opds:root/books/?filter=m → thin entries (no content/image/related)."""
        response = self.client.get(f'{OPDS_BASE}books/?filter=m')
        entries = _parse(response).findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        for entry in entries:
            self.assertIsNone(entry.find('atom:content', NS))
            self.assertEqual(len(_links_by_rel(entry, IMAGE_REL)), 0)
            self.assertEqual(len(_links_by_rel(entry, 'related')), 0)
            self.assertEqual(len(_links_by_rel(entry, THUMBNAIL_REL)), 1)

    def test_book_results_thick_param_makes_entries_complete(self):
        """GET opds:root/books/?filter=m&detail=thick → complete entries."""
        response = self.client.get(f'{OPDS_BASE}books/?filter=m&detail=thick')
        entries = _parse(response).findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        for entry in entries:
            self.assertEqual(len(_links_by_rel(entry, IMAGE_REL)), 1)
            self.assertEqual(len(_links_by_rel(entry, 'alternate')), 1)

    def test_book_results_thick_param_propagates_to_pagination(self):
        """GET opds:root/books/?filter=m&detail=thick → detail=thick on next link."""
        response = self.client.get(f'{OPDS_BASE}books/?filter=m&detail=thick')
        next_links = _get_link_hrefs(_parse(response), 'next')
        self.assertTrue(next_links, 'Expected a paginated feed with a next link')
        for href in next_links:
            self.assertIn('detail=thick', href)

    def test_book_results_thin_pagination_links_have_no_detail(self):
        """GET opds:root/books/?filter=m → pagination links carry no detail param."""
        response = self.client.get(f'{OPDS_BASE}books/?filter=m')
        next_links = _get_link_hrefs(_parse(response), 'next')
        self.assertTrue(next_links, 'Expected a paginated feed with a next link')
        for href in next_links:
            self.assertNotIn('detail=', href)


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
        # Anonymous root: Authors, Genres, Series, Books, Login.
        self.assertEqual(len(hrefs), 5)
        for href in hrefs:
            self.assertIn('detail=thick', href)

    def test_root_search_links_preserve_detail(self):
        """Both feed-level search links carry detail=thick under thick mode."""
        root = _parse(self.client.get(f'{OPDS_BASE}?detail=thick'))
        search_links = [
            lnk for lnk in root.findall('atom:link', NS)
            if lnk.get('rel') == 'search'
        ]
        description_link = next(
            lnk for lnk in search_links
            if lnk.get('type') == 'application/opensearchdescription+xml'
        )
        self.assertIn('detail=thick', description_link.get('href', ''))
        atom_link = next(
            lnk for lnk in search_links
            if lnk.get('type') == 'application/atom+xml'
        )
        # The templated link keeps its {searchTerms} placeholder *and* gains
        # the sticky detail=thick preference.
        self.assertIn('{searchTerms}', atom_link.get('href', ''))
        self.assertIn('detail=thick', atom_link.get('href', ''))

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
        self.assertGreater(len(hrefs), 1)  # synthetic "all A" + children
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
# OPDSAuthorScopedSeriesTest
# ---------------------------------------------------------------------------

class OPDSAuthorScopedSeriesTest(OPDSThrottleResetMixin, TestCase):
    """Author→series navigation is scoped to the author's books.

    Controlled dataset: one series shared by two authors.  Following a series
    entry from an author feed must list only *that author's* books in the
    series (``authors/<pk>/books/?series=<pk>``), while the full series (all
    authors) stays reachable at ``series/<pk>/``.
    """

    @classmethod
    def setUpTestData(cls):
        cls.lang = Language.objects.create(code='en', name='English')
        cls.asimov = Author.objects.create(first_name='Isaac', last_name='Asimov')
        cls.bradbury = Author.objects.create(first_name='Ray', last_name='Bradbury')
        cls.series = BookSeries.objects.create(name='Shared Series')

        # Asimov: two books in the series.
        for seq, title in enumerate(['A One', 'A Two'], start=1):
            book = Book.objects.create(title=title, language=cls.lang, file_type='epub')
            book.authors.add(cls.asimov)
            BookSeriesLink.objects.create(book=book, series=cls.series, sequence_number=seq)

        # Bradbury: one book in the SAME series — must never appear in Asimov's view.
        b_book = Book.objects.create(title='B One', language=cls.lang, file_type='epub')
        b_book.authors.add(cls.bradbury)
        BookSeriesLink.objects.create(book=b_book, series=cls.series, sequence_number=3)

        # Asimov standalone book (no series) — must not appear under ?series=<pk>.
        solo = Book.objects.create(title='A Solo', language=cls.lang, file_type='epub')
        solo.authors.add(cls.asimov)

    def _series_entry(self, author):
        """Return the per-series <entry> from *author*'s series feed."""
        root = _parse(self.client.get(f'{OPDS_BASE}authors/{author.pk}/series/'))
        prefix = f'{OPDS_BASE}authors/{author.pk}/books/?series='
        for entry in root.findall('atom:entry', NS):
            for lnk in entry.findall('atom:link', NS):
                href = lnk.get('href', '')
                if prefix in href and 'series=none' not in href:
                    return entry, lnk
        self.fail('No author-scoped series entry found')

    def test_author_series_entry_links_to_author_scoped_books(self):
        """The series entry links to authors/<pk>/books/?series=<pk> as an acquisition link."""
        _entry, link = self._series_entry(self.asimov)
        self.assertTrue(
            link.get('href', '').endswith(
                f'authors/{self.asimov.pk}/books/?series={self.series.pk}'
            ),
            msg=link.get('href'),
        )
        self.assertIn('kind=acquisition', link.get('type', ''))

    def test_author_series_entry_count_is_author_scoped(self):
        """Series entry <content> reports the author's count (2), not the series total (3)."""
        entry, _link = self._series_entry(self.asimov)
        content = entry.findtext('atom:content', namespaces=NS) or ''
        self.assertIn('2', content)
        self.assertNotIn('3', content)

    def test_author_scoped_series_lists_only_authors_books(self):
        """?series=<pk> returns only this author's books in the series (2 of 3)."""
        url = f'{OPDS_BASE}authors/{self.asimov.pk}/books/?series={self.series.pk}'
        root = _parse(self.client.get(url))
        titles = {e.findtext('atom:title', namespaces=NS) for e in root.findall('atom:entry', NS)}
        self.assertEqual(titles, {'A One', 'A Two'})

    def test_author_scoped_series_excludes_standalone(self):
        """The standalone book ('A Solo') is absent from the ?series=<pk> view."""
        url = f'{OPDS_BASE}authors/{self.asimov.pk}/books/?series={self.series.pk}'
        total = _count_all_pages(self.client, url)
        self.assertEqual(total, 2)

    def test_full_series_lists_all_authors_books(self):
        """series/<pk>/ still lists every author's books in the series (requirement #2)."""
        total = _count_all_pages(self.client, f'{OPDS_BASE}series/{self.series.pk}/')
        self.assertEqual(total, 3)

    def test_non_integer_series_param_ignored(self):
        """?series=abc is ignored → all of the author's books are returned (3)."""
        total = _count_all_pages(
            self.client, f'{OPDS_BASE}authors/{self.asimov.pk}/books/?series=abc'
        )
        self.assertEqual(total, 3)


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


# ---------------------------------------------------------------------------
# OPDSSeriesListFeedTest
# ---------------------------------------------------------------------------

class OPDSSeriesListFeedTest(OPDSThrottleResetMixin, TestCase):
    """Tests for the series alphabet-tree and flat results endpoints.

    Covers the three series browse endpoints:
    - ``opds:root/series/`` — flat, paginated navigation results
    - ``opds:root/series/tree/`` — alphabet tree root (navigation)
    - ``opds:root/series/tree/<name>/`` — alphabet sub-tree (navigation)

    Fixture: canonical dataset (148 series: C=54, S=62, T=11, 0-9=10,
    Other=11; no series starts with Z).
    """

    @classmethod
    def setUpTestData(cls):
        create_test_dataset()

    # ------------------------------------------------------------------
    # Tree root
    # ------------------------------------------------------------------

    @parameterized.expand([
        ('root', 'series/tree/'),       # alphabet tree root
        ('sub_node', 'series/tree/s/'),  # S=62 is expandable
    ])
    def test_series_tree_status_200(self, _name, path):
        """GET opds:root/series/tree/ and an expandable sub-node → HTTP 200."""
        response = self.client.get(f'{OPDS_BASE}{path}')
        self.assertEqual(response.status_code, 200)

    @parameterized.expand([
        ('list', 'series/?filter=t'),  # flat results
        ('tree', 'series/tree/'),       # alphabet tree root
    ])
    def test_series_feed_is_navigation(self, _name, path):
        """Flat series list and tree root Content-Type both contain kind=navigation."""
        response = self.client.get(f'{OPDS_BASE}{path}')
        self.assertIn('kind=navigation', response['Content-Type'])

    def test_series_alphabet_root_has_s_entry(self):
        """GET opds:root/series/tree/ → entry for 'S' with count 62."""
        response = self.client.get(f'{OPDS_BASE}series/tree/')
        entries = _parse(response).findall('atom:entry', NS)
        s_entry = next(
            (e for e in entries if e.findtext('atom:title', namespaces=NS) == 'S'),
            None,
        )
        self.assertIsNotNone(s_entry, 'Expected an "S" root entry')
        self.assertIn('62', s_entry.findtext('atom:content', namespaces=NS))

    def test_series_alphabet_root_no_entry_for_missing_letter(self):
        """GET opds:root/series/tree/ → no 'Z'/'z' root entry (no Z series)."""
        response = self.client.get(f'{OPDS_BASE}series/tree/')
        titles = _get_entry_titles(_parse(response))
        self.assertNotIn('Z', titles)
        self.assertNotIn('z', titles)

    def test_series_tree_entries_have_count_in_content(self):
        """Every opds:root/series/tree/ entry carries its item count in content."""
        response = self.client.get(f'{OPDS_BASE}series/tree/')
        entries = _parse(response).findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        for entry in entries:
            content = entry.findtext('atom:content', namespaces=NS) or ''
            self.assertRegex(content, r'\d+', f'Entry content {content!r} has no count')

    # ------------------------------------------------------------------
    # Tree sub-nodes
    # ------------------------------------------------------------------

    def test_series_s_is_expanded_subtree(self):
        """GET opds:root/series/tree/s/ → nav sub-entries, not a flat list of 62."""
        response = self.client.get(f'{OPDS_BASE}series/tree/s/')
        titles = set(_get_entry_titles(_parse(response)))
        self.assertEqual(titles, {'all S', 'Sh', 'St', 'Sw'})

    def test_series_st_sub_entries(self):
        """GET opds:root/series/tree/st/ → entries Sta, Ste, all St — no others."""
        response = self.client.get(f'{OPDS_BASE}series/tree/st/')
        titles = set(_get_entry_titles(_parse(response)))
        self.assertEqual(titles, {'all St', 'Sta', 'Ste'})

    @parameterized.expand([
        ('leaf_node', 't'),         # T=11 ≤ 50 is a leaf, never addressed by path
        ('nonexistent_node', 'z'),  # no Z node at all
    ])
    def test_series_tree_node_returns_404(self, _name, segment):
        """GET opds:root/series/tree/<leaf|missing>/ → HTTP 404."""
        response = self.client.get(f'{OPDS_BASE}series/tree/{segment}/')
        self.assertEqual(response.status_code, 404)

    def test_series_tree_sub_node_has_all_entry_first(self):
        """GET opds:root/series/tree/s/ → first entry is 'all S' with count 62."""
        response = self.client.get(f'{OPDS_BASE}series/tree/s/')
        entries = _parse(response).findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        self.assertEqual(entries[0].findtext('atom:title', namespaces=NS), 'all S')
        self.assertIn('62', entries[0].findtext('atom:content', namespaces=NS))

    def test_series_tree_sub_node_all_entry_links_to_filter(self):
        """The 'all S' entry in opds:root/series/tree/s/ links to ?filter=s."""
        response = self.client.get(f'{OPDS_BASE}series/tree/s/')
        all_entry = _parse(response).findall('atom:entry', NS)[0]
        hrefs = _get_link_hrefs(all_entry, 'subsection')
        self.assertTrue(
            any(h.endswith(f'{OPDS_BASE}series/?filter=s') for h in hrefs),
            msg=f'Expected series/?filter=s in {hrefs}',
        )

    @parameterized.expand([
        # Leaf child links to the flat ?filter= results.
        ('leaf_filter', 'Sh', 'series/?filter=sh'),
        # Expandable child links to its own sub-tree.
        ('expandable_subtree', 'St', 'series/tree/st/'),
    ])
    def test_series_tree_child_links_to(self, _name, child_title, href_suffix):
        """Each child in opds:root/series/tree/s/ links to its proper target."""
        response = self.client.get(f'{OPDS_BASE}series/tree/s/')
        entries = _parse(response).findall('atom:entry', NS)
        child = next(
            e for e in entries
            if e.findtext('atom:title', namespaces=NS) == child_title
        )
        hrefs = _get_link_hrefs(child, 'subsection')
        self.assertTrue(
            any(h.endswith(f'{OPDS_BASE}{href_suffix}') for h in hrefs),
            msg=f'Expected {href_suffix} in {hrefs}',
        )

    # ------------------------------------------------------------------
    # Flat results
    # ------------------------------------------------------------------

    def test_series_results_by_filter_status_200(self):
        """GET opds:root/series/?filter=t → HTTP 200 (T=11, leaf)."""
        response = self.client.get(f'{OPDS_BASE}series/?filter=t')
        self.assertEqual(response.status_code, 200)

    def test_series_results_has_correct_count(self):
        """GET opds:root/series/?filter=t → exactly 11 entries (T=11, one page)."""
        response = self.client.get(f'{OPDS_BASE}series/?filter=t')
        entries = _parse(response).findall('atom:entry', NS)
        self.assertEqual(len(entries), 11)

    def test_series_results_entry_links_to_series_detail(self):
        """Each entry in opds:root/series/?filter=t links to opds:root/series/<pk>/."""
        response = self.client.get(f'{OPDS_BASE}series/?filter=t')
        entries = _parse(response).findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        for entry in entries:
            hrefs = _get_link_hrefs(entry, 'subsection')
            self.assertTrue(
                any(f'{OPDS_BASE}series/' in h and h.rstrip('/').split('/')[-1].isdigit() for h in hrefs),
                msg=f'Entry links {hrefs!r} do not point to a series detail URL',
            )

    def test_series_results_empty_filter_returns_empty_feed(self):
        """GET opds:root/series/?filter=z → HTTP 200 with zero entries."""
        response = self.client.get(f'{OPDS_BASE}series/?filter=z')
        self.assertEqual(response.status_code, 200)
        entries = _parse(response).findall('atom:entry', NS)
        self.assertEqual(len(entries), 0)

    def test_series_digits_node_list(self):
        """GET opds:root/series/?regex=^[0-9] → 200 with exactly 10 entries."""
        response = self.client.get(f'{OPDS_BASE}series/?regex=^[0-9]')
        self.assertEqual(response.status_code, 200)
        entries = _parse(response).findall('atom:entry', NS)
        self.assertEqual(len(entries), 10)

    def test_series_full_set_no_filter_returns_paginated_results(self):
        """GET opds:root/series/ (no params) → 200 with a full first page of 20."""
        response = self.client.get(f'{OPDS_BASE}series/')
        self.assertEqual(response.status_code, 200)
        entries = _parse(response).findall('atom:entry', NS)
        self.assertEqual(len(entries), 20)

    def test_series_results_entry_content_has_book_count(self):
        """Each opds:root/series/?filter=t entry <content> carries its book count."""
        response = self.client.get(f'{OPDS_BASE}series/?filter=t')
        entries = _parse(response).findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        for entry in entries:
            entry_id = entry.findtext('atom:id', namespaces=NS) or ''
            pk = int(entry_id.split(':')[-1])
            expected = BookSeries.objects.get(pk=pk).books.count()
            content = entry.findtext('atom:content', namespaces=NS) or ''
            self.assertEqual(content, f'{expected} books')

    def test_series_results_zero_book_series_shows_count_0(self):
        """A series with no books still renders a mandatory count of 0."""
        BookSeries.objects.create(name='Zzz Empty')
        response = self.client.get(f'{OPDS_BASE}series/?filter=zzz')
        entries = _parse(response).findall('atom:entry', NS)
        self.assertEqual(len(entries), 1)
        content = entries[0].findtext('atom:content', namespaces=NS) or ''
        self.assertEqual(content, '0 books')


# ---------------------------------------------------------------------------
# OPDSSeriesDetailTest
# ---------------------------------------------------------------------------

class OPDSSeriesDetailTest(OPDSThrottleResetMixin, TestCase):
    """Tests for the series detail acquisition feed (docs/TDD_OPDS.md §6.4).

    Fixture: canonical dataset.  A series with at least two books (so the
    sequence ordering is observable) is found via ``.filter()``; one extra
    subseries is created inline so the subseries-navigation path is exercised.
    """

    @classmethod
    def setUpTestData(cls):
        create_test_dataset()
        cls.series = (
            BookSeries.objects
            .annotate(book_count=Count('books'))
            .filter(book_count__gte=2)
            .first()
        )
        cls.subseries = BookSeries.objects.create(
            name='SubTest', parent=cls.series,
        )

    def _book_entries(self, root):
        """Book (acquisition) entries — id of form tag:bookshelf:book:<pk>."""
        return [
            e for e in root.findall('atom:entry', NS)
            if (e.findtext('atom:id', namespaces=NS) or '').startswith('tag:bookshelf:book:')
        ]

    def _subseries_entries(self, root):
        """Subseries (navigation) entries — id of form tag:bookshelf:series:<pk>."""
        return [
            e for e in root.findall('atom:entry', NS)
            if (e.findtext('atom:id', namespaces=NS) or '').startswith('tag:bookshelf:series:')
        ]

    def test_series_detail_status_200(self):
        """GET opds:root/series/<pk>/ → HTTP 200."""
        response = self.client.get(f'{OPDS_BASE}series/{self.series.pk}/')
        self.assertEqual(response.status_code, 200)

    def test_series_detail_404(self):
        """GET opds:root/series/99999/ → HTTP 404."""
        response = self.client.get(f'{OPDS_BASE}series/99999/')
        self.assertEqual(response.status_code, 404)

    def test_series_detail_is_acquisition_feed(self):
        """Series detail Content-Type contains kind=acquisition."""
        response = self.client.get(f'{OPDS_BASE}series/{self.series.pk}/')
        self.assertIn('kind=acquisition', response['Content-Type'])

    def test_series_detail_has_subseries_nav_entry(self):
        """Feed contains the subseries as a navigation entry linking to its detail."""
        response = self.client.get(f'{OPDS_BASE}series/{self.series.pk}/')
        subentries = self._subseries_entries(_parse(response))
        target = next(
            (e for e in subentries
             if (e.findtext('atom:id', namespaces=NS) or '').endswith(f':{self.subseries.pk}')),
            None,
        )
        self.assertIsNotNone(target, 'Expected the subseries navigation entry')
        hrefs = _get_link_hrefs(target, 'subsection')
        self.assertTrue(
            any(h.endswith(f'{OPDS_BASE}series/{self.subseries.pk}/') for h in hrefs),
            msg=f'Expected subseries detail link in {hrefs}',
        )

    def test_series_detail_subseries_entry_has_count_and_logo(self):
        """The subseries navigation entry carries a count and the logo thumbnail."""
        response = self.client.get(f'{OPDS_BASE}series/{self.series.pk}/')
        target = next(
            e for e in self._subseries_entries(_parse(response))
            if (e.findtext('atom:id', namespaces=NS) or '').endswith(f':{self.subseries.pk}')
        )
        content = target.findtext('atom:content', namespaces=NS) or ''
        self.assertEqual(content, '0 books')
        logo_links = [
            lnk for lnk in _links_by_rel(target, THUMBNAIL_REL)
            if lnk.get('href', '').endswith(LOGO_HREF_SUFFIX)
        ]
        self.assertEqual(len(logo_links), 1)

    def test_series_detail_has_books(self):
        """Feed contains at least one book (acquisition) entry."""
        response = self.client.get(f'{OPDS_BASE}series/{self.series.pk}/')
        self.assertGreater(len(self._book_entries(_parse(response))), 0)

    def test_series_detail_books_sorted_by_sequence_number(self):
        """Book entries appear in ascending sequence_number order."""
        response = self.client.get(f'{OPDS_BASE}series/{self.series.pk}/')
        seqs = [
            int(e.findtext('atom:title', namespaces=NS).split(' ')[0].lstrip('#'))
            for e in self._book_entries(_parse(response))
        ]
        self.assertEqual(seqs, sorted(seqs))

    def test_series_detail_book_title_prefixed_with_seq(self):
        """Each book entry <title> starts with '#<seq> · '."""
        response = self.client.get(f'{OPDS_BASE}series/{self.series.pk}/')
        entries = self._book_entries(_parse(response))
        self.assertGreater(len(entries), 0)
        for entry in entries:
            title = entry.findtext('atom:title', namespaces=NS) or ''
            self.assertRegex(title, r'^#\d+ · ')

    def test_series_detail_acquisition_link_always_rendered(self):
        """Every series book entry exposes exactly one acquisition link."""
        response = self.client.get(f'{OPDS_BASE}series/{self.series.pk}/')
        entries = self._book_entries(_parse(response))
        self.assertGreater(len(entries), 0)
        for entry in entries:
            self.assertEqual(len(_links_by_rel(entry, ACQUISITION_REL)), 1)

    def test_series_detail_book_entries_thin_by_default(self):
        """Default series book entries are thin: no content/calibre/related."""
        response = self.client.get(f'{OPDS_BASE}series/{self.series.pk}/')
        entries = self._book_entries(_parse(response))
        self.assertGreater(len(entries), 0)
        for entry in entries:
            self.assertIsNone(entry.find('atom:content', NS))
            self.assertIsNone(entry.find('calibre:series', NS))
            self.assertEqual(len(_links_by_rel(entry, 'related')), 0)
            self.assertEqual(len(_links_by_rel(entry, IMAGE_REL)), 0)
            alt = _links_by_rel(entry, 'alternate')
            self.assertEqual(len(alt), 1)

    def test_series_detail_book_entries_thick_param(self):
        """?detail=thick makes series book entries complete (full image + related)."""
        response = self.client.get(f'{OPDS_BASE}series/{self.series.pk}/?detail=thick')
        entries = self._book_entries(_parse(response))
        self.assertGreater(len(entries), 0)
        for entry in entries:
            self.assertEqual(len(_links_by_rel(entry, IMAGE_REL)), 1)
            # The book is series-linked → carries a series rel="related" link.
            self.assertGreaterEqual(len(_links_by_rel(entry, 'related')), 1)


# ---------------------------------------------------------------------------
# OPDSGenreFeedTest
# ---------------------------------------------------------------------------

class OPDSGenreFeedTest(OPDSThrottleResetMixin, TestCase):
    """Tests for the genre hierarchy feeds (see docs/TDD_OPDS.md §6.2a).

    Covers:
    - ``opds:root/genres/`` — top-level genre navigation feed
    - ``opds:root/genres/<pk>/`` — subgenres-only navigation feed (leaf → 302)
    - ``opds:root/genres/<pk>/books/tree/[<name>/]`` — genre-scoped alphabet tree
    - ``opds:root/genres/<pk>/books/`` — flat genre book acquisition results

    Fixture: canonical dataset plus an inline ``genre_empty`` top-level genre
    (no subgenres, no books) used to exercise the ``count=0`` and empty-tree
    edges.

    Note: the genre-scoped alphabet tree is built from the genre's own
    (+descendant) book set, whose per-letter counts never exceed the
    ``get_alphabet_tree`` expansion threshold (50) below the first letter, so a
    single leaf genre's tree expands at most one level — the ``"alid"`` branch
    cited in the TDD test-table examples exists only in the global book tree.
    The ``Alid`` books remain reachable within a genre via the ``?filter=alid``
    results endpoint, which these tests assert directly.
    """

    @classmethod
    def setUpTestData(cls):
        create_test_dataset()
        cls.sf_fantasy = Genre.objects.get(code='sf_fantasy')
        cls.myst = Genre.objects.get(code='mysteries_thrillers')
        cls.action = Genre.objects.get(code='action_adventure')
        cls.dystopia = Genre.objects.get(code='dystopia')
        cls.sci_fi = Genre.objects.get(code='science_fiction')
        cls.fantasy = Genre.objects.get(code='fantasy')
        cls.nature_animals = Genre.objects.get(code='nature_animals')
        cls.genre_empty = Genre.objects.create(name='Empty Genre', code='empty_genre')

    # ------------------------------------------------------------------
    # Genre root feed
    # ------------------------------------------------------------------

    def test_genre_root_status_200(self):
        """GET opds:root/genres/ → HTTP 200."""
        response = self.client.get(f'{OPDS_BASE}genres/')
        self.assertEqual(response.status_code, 200)

    def test_genre_root_is_navigation(self):
        """GET opds:root/genres/ → Content-Type contains kind=navigation."""
        response = self.client.get(f'{OPDS_BASE}genres/')
        self.assertIn('kind=navigation', response['Content-Type'])

    def test_genre_root_lists_top_level_genres_only(self):
        """GET opds:root/genres/ → top-level genres present, leaf genres absent."""
        response = self.client.get(f'{OPDS_BASE}genres/')
        titles = set(_get_entry_titles(_parse(response)))
        self.assertIn(self.sf_fantasy.name, titles)
        self.assertIn(self.myst.name, titles)
        self.assertIn(self.action.name, titles)
        self.assertIn(self.genre_empty.name, titles)
        self.assertNotIn(self.dystopia.name, titles)
        self.assertNotIn(self.sci_fi.name, titles)

    def test_genre_root_entry_links_to_genre_detail(self):
        """Each opds:root/genres/ entry links to opds:root/genres/<pk>/."""
        response = self.client.get(f'{OPDS_BASE}genres/')
        entries = _parse(response).findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        for entry in entries:
            entry_id = entry.findtext('atom:id', namespaces=NS) or ''
            pk = entry_id.split(':')[-1]
            hrefs = _get_link_hrefs(entry, 'subsection')
            self.assertTrue(
                any(h.endswith(f'{OPDS_BASE}genres/{pk}/') for h in hrefs),
                msg=f'Expected genres/{pk}/ in {hrefs}',
            )

    def test_genre_root_entry_content_has_book_count(self):
        """The sf_fantasy entry <content> reports its descendant-inclusive count 279."""
        response = self.client.get(f'{OPDS_BASE}genres/')
        entries = _parse(response).findall('atom:entry', NS)
        sf_entry = next(
            e for e in entries
            if e.findtext('atom:title', namespaces=NS) == self.sf_fantasy.name
        )
        self.assertIn('279', sf_entry.findtext('atom:content', namespaces=NS))

    def test_genre_root_genre_with_no_books_still_listed(self):
        """genre_empty (no books) still appears in opds:root/genres/ with count 0."""
        response = self.client.get(f'{OPDS_BASE}genres/')
        entries = _parse(response).findall('atom:entry', NS)
        empty_entry = next(
            e for e in entries
            if e.findtext('atom:title', namespaces=NS) == self.genre_empty.name
        )
        self.assertIn('0', empty_entry.findtext('atom:content', namespaces=NS))

    def test_genre_root_entries_have_logo_thumbnail(self):
        """Every opds:root/genres/ entry carries the logo thumbnail link."""
        response = self.client.get(f'{OPDS_BASE}genres/')
        entries = _parse(response).findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        for entry in entries:
            hrefs = _get_link_hrefs(entry, THUMBNAIL_REL)
            self.assertTrue(
                any(h.endswith(LOGO_HREF_SUFFIX) for h in hrefs),
                msg=f'Entry missing logo thumbnail: {hrefs}',
            )

    # ------------------------------------------------------------------
    # Genre detail feed (subgenres only)
    # ------------------------------------------------------------------

    def test_genre_detail_with_subgenres_status_200(self):
        """GET opds:root/genres/<sf_fantasy.pk>/ → HTTP 200 (has subgenres)."""
        response = self.client.get(f'{OPDS_BASE}genres/{self.sf_fantasy.pk}/')
        self.assertEqual(response.status_code, 200)

    def test_genre_detail_404(self):
        """GET opds:root/genres/99999/ → HTTP 404 (unknown genre)."""
        response = self.client.get(f'{OPDS_BASE}genres/99999/')
        self.assertEqual(response.status_code, 404)

    def test_genre_detail_lists_subgenres_only(self):
        """sf_fantasy detail lists exactly its 3 subgenres, each linking to its detail."""
        response = self.client.get(f'{OPDS_BASE}genres/{self.sf_fantasy.pk}/')
        root = _parse(response)
        titles = set(_get_entry_titles(root))
        self.assertEqual(
            titles,
            {self.dystopia.name, self.sci_fi.name, self.fantasy.name},
        )
        for entry in root.findall('atom:entry', NS):
            entry_id = entry.findtext('atom:id', namespaces=NS) or ''
            pk = entry_id.split(':')[-1]
            hrefs = _get_link_hrefs(entry, 'subsection')
            self.assertTrue(
                any(h.endswith(f'{OPDS_BASE}genres/{pk}/') for h in hrefs),
                msg=f'Expected genres/{pk}/ in {hrefs}',
            )

    def test_genre_detail_has_no_book_or_alphabet_entries(self):
        """sf_fantasy detail has no acquisition entries and no alphabet-tree nodes."""
        response = self.client.get(f'{OPDS_BASE}genres/{self.sf_fantasy.pk}/')
        root = _parse(response)
        titles = set(_get_entry_titles(root))
        self.assertNotIn('Alid', titles)
        self.assertNotIn('A', titles)
        for entry in root.findall('atom:entry', NS):
            self.assertEqual(len(_links_by_rel(entry, ACQUISITION_REL)), 0)

    @parameterized.expand([
        ('leaf', 'dystopia'),      # leaf genre (has books, no subgenres)
        ('empty', 'genre_empty'),  # no subgenres and no books
    ])
    def test_genre_detail_without_subgenres_redirects_to_book_tree(self, _name, attr):
        """GET opds:root/genres/<pk>/ with no subgenres → 302 to its books/tree/."""
        genre = getattr(self, attr)
        response = self.client.get(f'{OPDS_BASE}genres/{genre.pk}/')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response['Location'].endswith(f'{OPDS_BASE}genres/{genre.pk}/books/tree/')
        )

    def test_genre_detail_redirect_preserves_detail_thick(self):
        """A leaf-genre 302 carries ?detail=thick over to the books/tree/ URL."""
        response = self.client.get(f'{OPDS_BASE}genres/{self.dystopia.pk}/?detail=thick')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response['Location'],
            f'{OPDS_BASE}genres/{self.dystopia.pk}/books/tree/?detail=thick',
        )

    # ------------------------------------------------------------------
    # Genre book tree (navigation)
    # ------------------------------------------------------------------

    def test_genre_book_tree_status_200_navigation(self):
        """GET opds:root/genres/<sf_fantasy.pk>/books/tree/ → 200, kind=navigation."""
        response = self.client.get(f'{OPDS_BASE}genres/{self.sf_fantasy.pk}/books/tree/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('kind=navigation', response['Content-Type'])

    def test_genre_book_tree_has_alphabet_entries(self):
        """sf_fantasy book tree has an expandable 'A' node; its sub-tree shows 'Al'."""
        response = self.client.get(f'{OPDS_BASE}genres/{self.sf_fantasy.pk}/books/tree/')
        root = _parse(response)
        a_entry = next(
            e for e in root.findall('atom:entry', NS)
            if e.findtext('atom:title', namespaces=NS) == 'A'
        )
        a_hrefs = _get_link_hrefs(a_entry, 'subsection')
        self.assertTrue(
            any(h.endswith(f'{OPDS_BASE}genres/{self.sf_fantasy.pk}/books/tree/a/')
                for h in a_hrefs),
            msg=f'Expected expandable A node in {a_hrefs}',
        )
        sub = self.client.get(f'{OPDS_BASE}genres/{self.sf_fantasy.pk}/books/tree/a/')
        self.assertIn('Al', set(_get_entry_titles(_parse(sub))))

    def test_genre_book_tree_only_contains_own_books(self):
        """dystopia book tree shows only its own letters with matching counts."""
        response = self.client.get(f'{OPDS_BASE}genres/{self.dystopia.pk}/books/tree/')
        root = _parse(response)
        titles = set(_get_entry_titles(root))
        self.assertEqual(titles, {'A', 'B', 'M', 'П', '0-9', 'Other'})
        entries = {
            e.findtext('atom:title', namespaces=NS): e
            for e in root.findall('atom:entry', NS)
        }
        self.assertIn('46', entries['A'].findtext('atom:content', namespaces=NS))
        self.assertIn('10', entries['M'].findtext('atom:content', namespaces=NS))

    @parameterized.expand([
        ('leaf_node', 'a'),         # dystopia A=46 ≤ 50 is a leaf, never path-addressable
        ('nonexistent_node', 'z'),  # no Z node in dystopia
    ])
    def test_genre_book_tree_node_returns_404(self, _name, segment):
        """GET opds:root/genres/<dystopia.pk>/books/tree/<leaf|missing>/ → HTTP 404."""
        response = self.client.get(
            f'{OPDS_BASE}genres/{self.dystopia.pk}/books/tree/{segment}/'
        )
        self.assertEqual(response.status_code, 404)

    def test_genre_book_tree_empty_genre_returns_empty_tree(self):
        """GET opds:root/genres/<genre_empty.pk>/books/tree/ → 200 with 0 entries."""
        response = self.client.get(f'{OPDS_BASE}genres/{self.genre_empty.pk}/books/tree/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(_parse(response).findall('atom:entry', NS)), 0)

    def test_genre_book_tree_leaf_links_to_results(self):
        """A leaf letter node ('M') links to opds:root/genres/<pk>/books/?filter=m."""
        response = self.client.get(f'{OPDS_BASE}genres/{self.sf_fantasy.pk}/books/tree/')
        m_entry = next(
            e for e in _parse(response).findall('atom:entry', NS)
            if e.findtext('atom:title', namespaces=NS) == 'M'
        )
        hrefs = _get_link_hrefs(m_entry, 'subsection')
        self.assertTrue(
            any(h.endswith(f'{OPDS_BASE}genres/{self.sf_fantasy.pk}/books/?filter=m')
                for h in hrefs),
            msg=f'Expected genre book filter results in {hrefs}',
        )

    def test_genre_book_tree_non_leaf_links_to_subtree(self):
        """An expandable 'A' node links to its sub-tree, which has a synthetic 'all A'."""
        response = self.client.get(f'{OPDS_BASE}genres/{self.sf_fantasy.pk}/books/tree/')
        a_entry = next(
            e for e in _parse(response).findall('atom:entry', NS)
            if e.findtext('atom:title', namespaces=NS) == 'A'
        )
        hrefs = _get_link_hrefs(a_entry, 'subsection')
        self.assertTrue(
            any(h.endswith(f'{OPDS_BASE}genres/{self.sf_fantasy.pk}/books/tree/a/')
                for h in hrefs),
        )
        sub = self.client.get(f'{OPDS_BASE}genres/{self.sf_fantasy.pk}/books/tree/a/')
        first = _parse(sub).findall('atom:entry', NS)[0]
        self.assertEqual(first.findtext('atom:title', namespaces=NS), 'all A')

    def test_genre_book_tree_regex_node_link_carries_regex_param(self):
        """The '0-9' leaf links via ?regex=; the 'Other' node links to its sub-tree."""
        response = self.client.get(f'{OPDS_BASE}genres/{self.sf_fantasy.pk}/books/tree/')
        entries = {
            e.findtext('atom:title', namespaces=NS): e
            for e in _parse(response).findall('atom:entry', NS)
        }
        digit_hrefs = _get_link_hrefs(entries['0-9'], 'subsection')
        self.assertTrue(
            any(f'{OPDS_BASE}genres/{self.sf_fantasy.pk}/books/?regex=' in h
                for h in digit_hrefs),
            msg=f'Expected a ?regex= results link in {digit_hrefs}',
        )
        other_hrefs = _get_link_hrefs(entries['Other'], 'subsection')
        self.assertTrue(
            any(h.endswith(f'{OPDS_BASE}genres/{self.sf_fantasy.pk}/books/tree/other/')
                for h in other_hrefs),
            msg=f'Expected other sub-tree link in {other_hrefs}',
        )

    # ------------------------------------------------------------------
    # Genre book results (acquisition)
    # ------------------------------------------------------------------

    def test_genre_books_results_is_acquisition_feed(self):
        """GET opds:root/genres/<pk>/books/?filter=alid → kind=acquisition."""
        response = self.client.get(
            f'{OPDS_BASE}genres/{self.dystopia.pk}/books/?filter=alid'
        )
        self.assertIn('kind=acquisition', response['Content-Type'])

    def test_genre_books_results_by_filter_status_200(self):
        """GET opds:root/genres/<dystopia.pk>/books/?filter=alid → HTTP 200."""
        response = self.client.get(
            f'{OPDS_BASE}genres/{self.dystopia.pk}/books/?filter=alid'
        )
        self.assertEqual(response.status_code, 200)

    def test_genre_books_results_by_filter_filters_correctly(self):
        """dystopia ?filter=alid → all titles start 'Alid', none start 'Alit'."""
        response = self.client.get(
            f'{OPDS_BASE}genres/{self.dystopia.pk}/books/?filter=alid'
        )
        titles = _get_entry_titles(_parse(response))
        self.assertTrue(titles)
        for title in titles:
            self.assertTrue(title.lower().startswith('alid'), msg=f'Unexpected {title!r}')

    def test_genre_books_results_empty_filter_returns_empty_feed(self):
        """GET opds:root/genres/<dystopia.pk>/books/?filter=z → 200 with 0 entries."""
        response = self.client.get(
            f'{OPDS_BASE}genres/{self.dystopia.pk}/books/?filter=z'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(_parse(response).findall('atom:entry', NS)), 0)

    def test_genre_books_results_by_regex_filters_by_regex(self):
        """dystopia ?regex=^[0-9] → total equals the 0-9 tree count (2); digit titles."""
        total = _count_all_pages(
            self.client,
            f'{OPDS_BASE}genres/{self.dystopia.pk}/books/?regex=^[0-9]',
        )
        self.assertEqual(total, 2)
        response = self.client.get(
            f'{OPDS_BASE}genres/{self.dystopia.pk}/books/?regex=^[0-9]'
        )
        for title in _get_entry_titles(_parse(response)):
            self.assertTrue(title[0].isdigit(), msg=f'Non-digit title {title!r}')

    def test_genre_books_results_regex_beats_filter(self):
        """dystopia ?filter=0-9 (no regex) → istartswith yields 0 entries."""
        response = self.client.get(
            f'{OPDS_BASE}genres/{self.dystopia.pk}/books/?filter=0-9'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(_parse(response).findall('atom:entry', NS)), 0)

    def test_genre_books_results_thin_by_default(self):
        """GET opds:root/genres/<pk>/books/?filter=alid → thin entries by default."""
        response = self.client.get(
            f'{OPDS_BASE}genres/{self.dystopia.pk}/books/?filter=alid'
        )
        entries = _parse(response).findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        for entry in entries:
            self.assertIsNone(entry.find('atom:content', NS))
            self.assertEqual(len(_links_by_rel(entry, IMAGE_REL)), 0)
            self.assertEqual(len(_links_by_rel(entry, 'alternate')), 1)

    def test_genre_books_results_thick_param_makes_entries_complete(self):
        """GET opds:root/genres/<pk>/books/?filter=alid&detail=thick → complete entries."""
        response = self.client.get(
            f'{OPDS_BASE}genres/{self.dystopia.pk}/books/?filter=alid&detail=thick'
        )
        entries = _parse(response).findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        for entry in entries:
            self.assertEqual(len(_links_by_rel(entry, IMAGE_REL)), 1)


# ---------------------------------------------------------------------------
# OPDSGenreFeedCountsTest
# ---------------------------------------------------------------------------

class OPDSGenreFeedCountsTest(OPDSThrottleResetMixin, TestCase):
    """Verifies genre book counts against docs/library/tests/test_template.md.

    All counts are distinct books per genre (a multi-genre book is counted in
    each of its genres).  Fixture: canonical dataset.
    """

    @classmethod
    def setUpTestData(cls):
        create_test_dataset()
        cls.sf_fantasy = Genre.objects.get(code='sf_fantasy')
        cls.myst = Genre.objects.get(code='mysteries_thrillers')
        cls.action = Genre.objects.get(code='action_adventure')
        cls.dystopia = Genre.objects.get(code='dystopia')
        cls.fantasy = Genre.objects.get(code='fantasy')
        cls.nature_animals = Genre.objects.get(code='nature_animals')

    def _root_entry_content(self, genre):
        response = self.client.get(f'{OPDS_BASE}genres/')
        entries = _parse(response).findall('atom:entry', NS)
        entry = next(
            e for e in entries
            if e.findtext('atom:title', namespaces=NS) == genre.name
        )
        return entry.findtext('atom:content', namespaces=NS)

    @parameterized.expand([
        ('sf_fantasy', 'sf_fantasy', '279'),  # 116+82+81
        ('mysteries', 'myst', '208'),         # 130+78
        ('action_adv', 'action', '185'),      # 111+74
    ])
    def test_genre_root_descendant_inclusive_count(self, _name, attr, count):
        """Top-level genre root entry reports its descendant-inclusive book count."""
        self.assertIn(count, self._root_entry_content(getattr(self, attr)))

    def test_fantasy_book_tree_no_yu_entry(self):
        """fantasy book tree (root + Other sub-tree) contains no 'Ю' entry."""
        root = self.client.get(f'{OPDS_BASE}genres/{self.fantasy.pk}/books/tree/')
        self.assertNotIn('Ю', set(_get_entry_titles(_parse(root))))
        other = self.client.get(
            f'{OPDS_BASE}genres/{self.fantasy.pk}/books/tree/other/'
        )
        self.assertNotIn('Ю', set(_get_entry_titles(_parse(other))))

    def test_nature_animals_book_tree_total_is_74(self):
        """nature_animals book tree top-level entry counts sum to 74."""
        response = self.client.get(
            f'{OPDS_BASE}genres/{self.nature_animals.pk}/books/tree/'
        )
        entries = _parse(response).findall('atom:entry', NS)
        total = 0
        for entry in entries:
            title = entry.findtext('atom:title', namespaces=NS) or ''
            if title.startswith('all '):
                continue
            content = entry.findtext('atom:content', namespaces=NS) or '0'
            total += int(''.join(ch for ch in content if ch.isdigit()))
        self.assertEqual(total, 74)

    @parameterized.expand([
        ('alid', 'alid', 5),  # the 'Alid' group cited in TDD
        ('alit', 'alit', 7),
    ])
    def test_genre_books_results_dystopia_filter_count(self, _name, filter_value, expected):
        """dystopia ?filter=<value> → feed total (across pages) matches expected."""
        total = _count_all_pages(
            self.client,
            f'{OPDS_BASE}genres/{self.dystopia.pk}/books/?filter={filter_value}',
        )
        self.assertEqual(total, expected)


# ---------------------------------------------------------------------------
# OPDSSearchTest
# ---------------------------------------------------------------------------

def _find_section_entry(root_el, label_prefix):
    """Return the first <entry> whose <title> starts with *label_prefix*."""
    for entry in root_el.findall('atom:entry', NS):
        title = entry.findtext('atom:title', namespaces=NS) or ''
        if title.startswith(label_prefix):
            return entry
    return None


class OPDSSearchTest(OPDSThrottleResetMixin, TestCase):
    """Tests the search root feed and the three paginated search sub-feeds.

    Fixture: canonical dataset.  Query prefixes are chosen to exist in the
    dataset — ``Abak`` matches authors, ``Ch`` matches series, ``Alid`` matches
    book titles.  A unique ``Zap`` prefix (absent from the dataset) drives the
    pagination assertions via 25 fresh books created per-test in ``setUp``.
    """

    @classmethod
    def setUpTestData(cls):
        create_test_dataset()
        cls.lang = Language.objects.first()

    def setUp(self):
        super().setUp()
        # 25 fresh "Zap…" books per test to exercise pagination (page_size=20).
        Book.objects.bulk_create([
            Book(title=f'Zap Book {i:02d}', language=self.lang)
            for i in range(25)
        ])

    # ---- search root feed ----

    def test_search_root_returns_200(self):
        """GET opds:root/search/?q=Abak → 200."""
        response = self.client.get(f'{OPDS_BASE}search/?q=Abak')
        self.assertEqual(response.status_code, 200)

    @parameterized.expand([
        ('books', 'Alid', 'Books ('),   # matches books only
        ('series', 'Ch', 'Series ('),   # matches series only
        ('authors', 'Abak', 'Authors ('),  # matches authors only
    ])
    def test_search_root_has_section_entry(self, section, query, label):
        """?q=<query> → a '<label>N found)' entry linking to search/<section>/?q=<query>."""
        response = self.client.get(f'{OPDS_BASE}search/?q={query}')
        entry = _find_section_entry(_parse(response), label)
        self.assertIsNotNone(entry)
        hrefs = _get_link_hrefs(entry, 'subsection')
        self.assertTrue(
            any(h.endswith(f'{OPDS_BASE}search/{section}/?q={query}') for h in hrefs),
            msg=hrefs,
        )

    def test_search_root_section_omitted_when_empty(self):
        """?q=Abak → no 'Books' and no 'Series' section entry (authors only)."""
        root = _parse(self.client.get(f'{OPDS_BASE}search/?q=Abak'))
        self.assertIsNone(_find_section_entry(root, 'Books ('))
        self.assertIsNone(_find_section_entry(root, 'Series ('))

    def test_search_root_section_count_reflects_match_total(self):
        """?q=Abak → the Authors section label reports the real match count (21)."""
        root = _parse(self.client.get(f'{OPDS_BASE}search/?q=Abak'))
        title = _find_section_entry(root, 'Authors (').findtext('atom:title', namespaces=NS)
        self.assertEqual(title, 'Authors (21 found)')

    @parameterized.expand([
        ('whitespace_query', 'search/?q=%20%20%20'),  # q stripped to empty
        ('empty_query', 'search/'),                    # no q at all
        ('no_results', 'search/?q=xyzzyunmatchable'),  # q matches nothing
    ])
    def test_search_root_returns_empty_feed(self, _name, path):
        """An empty/blank/no-match query → 200 with 0 entries (never an error)."""
        response = self.client.get(f'{OPDS_BASE}{path}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(_parse(response).findall('atom:entry', NS)), 0)

    def test_search_root_is_navigation_feed(self):
        """The search root feed advertises kind=navigation."""
        response = self.client.get(f'{OPDS_BASE}search/?q=Abak')
        self.assertIn('kind=navigation', response['Content-Type'])

    def test_search_section_entries_have_logo(self):
        """Search section entries carry the logo thumbnail link."""
        root = _parse(self.client.get(f'{OPDS_BASE}search/?q=Abak'))
        entry = _find_section_entry(root, 'Authors (')
        thumbs = _get_link_hrefs(entry, THUMBNAIL_REL)
        self.assertTrue(any(h.endswith(LOGO_HREF_SUFFIX) for h in thumbs), msg=thumbs)

    # ---- author / series sub-feeds ----

    def test_search_authors_subfeed_entries_link_to_author(self):
        """search/authors/?q=Abak → each entry links to opds:root/authors/<pk>/."""
        root = _parse(self.client.get(f'{OPDS_BASE}search/authors/?q=Abak'))
        entries = root.findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        for entry in entries:
            hrefs = _get_link_hrefs(entry, 'subsection')
            self.assertTrue(
                any(f'{OPDS_BASE}authors/' in h for h in hrefs), msg=hrefs
            )

    def test_search_authors_subfeed_is_navigation(self):
        """The search-authors sub-feed advertises kind=navigation."""
        response = self.client.get(f'{OPDS_BASE}search/authors/?q=Abak')
        self.assertIn('kind=navigation', response['Content-Type'])

    def test_search_series_subfeed_entries_link_to_series(self):
        """search/series/?q=Ch → each entry links to opds:root/series/<pk>/."""
        root = _parse(self.client.get(f'{OPDS_BASE}search/series/?q=Ch'))
        entries = root.findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        for entry in entries:
            hrefs = _get_link_hrefs(entry, 'subsection')
            self.assertTrue(
                any(f'{OPDS_BASE}series/' in h for h in hrefs), msg=hrefs
            )

    # ---- book sub-feed ----

    def test_search_books_subfeed_is_acquisition(self):
        """The search-books sub-feed advertises kind=acquisition."""
        response = self.client.get(f'{OPDS_BASE}search/books/?q=Alid')
        self.assertIn('kind=acquisition', response['Content-Type'])

    def test_search_books_subfeed_acquisition_link_always_rendered(self):
        """Book entries always carry the acquisition link (catalog is public)."""
        root = _parse(self.client.get(f'{OPDS_BASE}search/books/?q=Alid'))
        entries = root.findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        for entry in entries:
            self.assertEqual(len(_links_by_rel(entry, ACQUISITION_REL)), 1)

    def test_search_books_subfeed_is_case_insensitive(self):
        """A lowercase q matches mixed-case titles (icontains): alid → 23 books."""
        total = _count_all_pages(self.client, f'{OPDS_BASE}search/books/?q=alid')
        self.assertEqual(total, 23)

    def test_search_books_subfeed_matches_substring(self):
        """Matching is substring, not prefix: q=lid still finds the Alid* titles."""
        total = _count_all_pages(self.client, f'{OPDS_BASE}search/books/?q=lid')
        self.assertEqual(total, 23)

    def test_search_books_subfeed_excludes_non_matching(self):
        """Every returned entry actually matches q; non-matching titles are absent."""
        titles = []
        for url in (f'{OPDS_BASE}search/books/?q=Alid',
                    f'{OPDS_BASE}search/books/?q=Alid&page=2'):
            root = _parse(self.client.get(url))
            titles += [e.findtext('atom:title', namespaces=NS) for e in root.findall('atom:entry', NS)]
        self.assertEqual(len(titles), 23)
        self.assertTrue(all('Alid' in t for t in titles), msg=titles)

    def test_search_books_subfeed_thin_by_default(self):
        """search/books/?q=Alid → thin entries (no content / full image)."""
        root = _parse(self.client.get(f'{OPDS_BASE}search/books/?q=Alid'))
        entries = root.findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        for entry in entries:
            self.assertIsNone(entry.find('atom:content', NS))
            self.assertEqual(len(_links_by_rel(entry, IMAGE_REL)), 0)
            self.assertEqual(len(_links_by_rel(entry, 'alternate')), 1)

    def test_search_books_subfeed_thick_param(self):
        """search/books/?q=Alid&detail=thick → complete (thick) entries."""
        root = _parse(self.client.get(f'{OPDS_BASE}search/books/?q=Alid&detail=thick'))
        entries = root.findall('atom:entry', NS)
        self.assertGreater(len(entries), 0)
        for entry in entries:
            self.assertEqual(len(_links_by_rel(entry, IMAGE_REL)), 1)

    def test_search_books_subfeed_pagination(self):
        """search/books/?q=Zap page 1 has 20 entries with a next link."""
        root = _parse(self.client.get(f'{OPDS_BASE}search/books/?q=Zap'))
        self.assertEqual(len(root.findall('atom:entry', NS)), 20)
        self.assertTrue(_get_link_hrefs(root, 'next'))

    def test_search_books_subfeed_total_matches_count(self):
        """search/books/?q=Zap returns all 25 created books across pages."""
        total = _count_all_pages(self.client, f'{OPDS_BASE}search/books/?q=Zap')
        self.assertEqual(total, 25)

    # ---- cross-cutting sub-feed behavior ----

    @parameterized.expand([
        ('authors', 'search/authors/?q=Aban', 'Aban'),  # 39 matching authors
        ('series', 'search/series/?q=Ch', 'Ch'),         # 36 matching series
        ('books', 'search/books/?q=Zap', 'Zap'),         # 25 matching books
    ])
    def test_search_subfeed_pagination_preserves_q(self, _name, path, query):
        """Every paginated sub-feed's next link preserves both q and page=2."""
        root = _parse(self.client.get(f'{OPDS_BASE}{path}'))
        next_href = _get_link_hrefs(root, 'next')[0]
        self.assertIn(f'q={query}', next_href)
        self.assertIn('page=2', next_href)

    def test_search_subfeed_empty_query_returns_empty_feed(self):
        """GET search/books/ (no q) → 200 with 0 entries."""
        response = self.client.get(f'{OPDS_BASE}search/books/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(_parse(response).findall('atom:entry', NS)), 0)

    # ---- end-to-end: all three sections + drill-down ----

    def test_search_all_sections_present_and_drilldown(self):
        """A query matching all entity types lists every section, then each
        ``search/<section>/`` sub-feed resolves to the matching element.

        One author, one series, and one book share the unique token ``Quokka``,
        so the root feed must surface ``Authors (1 found)``, ``Series (1 found)``
        and ``Books (1 found)`` together — and following each section link must
        yield a feed whose entry is the exact object that matched.
        """
        # Arrange — one match per entity type, sharing a unique token.
        author = Author.objects.create(first_name='Sam', last_name='Quokka')
        series = BookSeries.objects.create(name='Quokka Saga')
        book = Book.objects.create(title='Quokka Tales', language=self.lang)

        # Act / Assert — root lists all three sections with the right counts + links.
        root = _parse(self.client.get(f'{OPDS_BASE}search/?q=Quokka'))
        expected = {
            'Authors (1 found)': f'{OPDS_BASE}search/authors/?q=Quokka',
            'Series (1 found)': f'{OPDS_BASE}search/series/?q=Quokka',
            'Books (1 found)': f'{OPDS_BASE}search/books/?q=Quokka',
        }
        for label, sub_url in expected.items():
            entry = _find_section_entry(root, label)
            self.assertIsNotNone(entry, msg=f'missing section {label!r}')
            hrefs = _get_link_hrefs(entry, 'subsection')
            self.assertTrue(any(h.endswith(sub_url) for h in hrefs), msg=hrefs)

        # Assert — drilling into the authors sub-feed yields exactly the author.
        authors_feed = _parse(self.client.get(f'{OPDS_BASE}search/authors/?q=Quokka'))
        author_entries = authors_feed.findall('atom:entry', NS)
        self.assertEqual(len(author_entries), 1)
        self.assertEqual(author_entries[0].findtext('atom:title', namespaces=NS), author.full_name)
        self.assertTrue(any(
            h.endswith(f'{OPDS_BASE}authors/{author.pk}/')
            for h in _get_link_hrefs(author_entries[0], 'subsection')
        ))

        # Assert — drilling into the series sub-feed yields exactly the series.
        series_feed = _parse(self.client.get(f'{OPDS_BASE}search/series/?q=Quokka'))
        series_entries = series_feed.findall('atom:entry', NS)
        self.assertEqual(len(series_entries), 1)
        self.assertTrue(any(
            h.endswith(f'{OPDS_BASE}series/{series.pk}/')
            for h in _get_link_hrefs(series_entries[0], 'subsection')
        ))

        # Assert — drilling into the books sub-feed yields exactly the book,
        # carrying its acquisition link.
        books_feed = _parse(self.client.get(f'{OPDS_BASE}search/books/?q=Quokka'))
        book_entries = books_feed.findall('atom:entry', NS)
        self.assertEqual(len(book_entries), 1)
        self.assertEqual(book_entries[0].findtext('atom:title', namespaces=NS), book.title)
        self.assertEqual(len(_links_by_rel(book_entries[0], ACQUISITION_REL)), 1)


# ---------------------------------------------------------------------------
# OPDSOpenSearchDescriptionTest
# ---------------------------------------------------------------------------

class OPDSOpenSearchDescriptionTest(OPDSThrottleResetMixin, TestCase):
    """Tests the OpenSearch description document endpoint (no DB required)."""

    def test_opensearch_description_status_200(self):
        """GET opds:root/search/description.xml → 200."""
        response = self.client.get(f'{OPDS_BASE}search/description.xml')
        self.assertEqual(response.status_code, 200)

    def test_opensearch_description_content_type(self):
        """Content-Type is application/opensearchdescription+xml."""
        response = self.client.get(f'{OPDS_BASE}search/description.xml')
        self.assertTrue(
            response['Content-Type'].startswith(
                'application/opensearchdescription+xml'
            ),
            msg=response['Content-Type'],
        )

    def test_opensearch_description_has_shortname(self):
        """The document's <ShortName> element text is 'Bookshelf'."""
        response = self.client.get(f'{OPDS_BASE}search/description.xml')
        ns = {'os': 'http://a9.com/-/spec/opensearch/1.1/'}
        root = ET.fromstring(response.content)
        self.assertEqual(root.findtext('os:ShortName', namespaces=ns), 'Bookshelf')

    def test_opensearch_description_has_url_template(self):
        """The <Url> template points at the search root (chooser feed)."""
        response = self.client.get(f'{OPDS_BASE}search/description.xml')
        ns = {'os': 'http://a9.com/-/spec/opensearch/1.1/'}
        url_el = ET.fromstring(response.content).find('os:Url', ns)
        self.assertIsNotNone(url_el)
        self.assertIn(
            f'{OPDS_BASE}search/?q={{searchTerms}}',
            url_el.get('template', ''),
        )
        # Must not collapse onto a sub-feed (e.g. books-only).
        self.assertNotIn('search/books/', url_el.get('template', ''))

    def test_opensearch_description_url_type_is_opds_catalog(self):
        """OPDS 1.2: the <Url> type must be the OPDS Catalog media type.

        Plain ``application/atom+xml`` is rejected by spec-compliant readers,
        which then surface no search.  The search root is a navigation feed.
        """
        response = self.client.get(f'{OPDS_BASE}search/description.xml')
        ns = {'os': 'http://a9.com/-/spec/opensearch/1.1/'}
        url_el = ET.fromstring(response.content).find('os:Url', ns)
        self.assertEqual(
            url_el.get('type'),
            'application/atom+xml;profile=opds-catalog;kind=navigation',
        )

    def test_opensearch_description_template_is_absolute_url(self):
        """The Url template is an absolute http(s) URL."""
        response = self.client.get(f'{OPDS_BASE}search/description.xml')
        ns = {'os': 'http://a9.com/-/spec/opensearch/1.1/'}
        url_el = ET.fromstring(response.content).find('os:Url', ns)
        self.assertTrue(url_el.get('template', '').startswith('http'))

    def test_opensearch_description_template_bakes_detail_thick(self):
        """With ?detail=thick the Url template carries q={searchTerms} and detail=thick."""
        response = self.client.get(f'{OPDS_BASE}search/description.xml?detail=thick')
        ns = {'os': 'http://a9.com/-/spec/opensearch/1.1/'}
        url_el = ET.fromstring(response.content).find('os:Url', ns)
        template = url_el.get('template', '')
        self.assertIn('q={searchTerms}', template)
        self.assertIn('detail=thick', template)

    def test_opensearch_description_template_omits_detail_by_default(self):
        """Without ?detail=thick the Url template has no detail parameter."""
        response = self.client.get(f'{OPDS_BASE}search/description.xml')
        ns = {'os': 'http://a9.com/-/spec/opensearch/1.1/'}
        url_el = ET.fromstring(response.content).find('os:Url', ns)
        self.assertNotIn('detail', url_el.get('template', ''))

    def test_opensearch_description_uses_default_namespace(self):
        """Tags are unprefixed under a default xmlns (spec/Flibusta form).

        Some OPDS readers naively string-match for an unprefixed
        ``<Url template>`` and fail to discover search when the elements
        carry an ``opensearch:`` prefix.
        """
        response = self.client.get(f'{OPDS_BASE}search/description.xml')
        body = response.content.decode()
        self.assertIn(
            '<OpenSearchDescription xmlns='
            '"http://a9.com/-/spec/opensearch/1.1/"',
            body,
        )
        self.assertIn('<Url ', body)
        self.assertNotIn('opensearch:', body)
        self.assertNotIn('ns0:', body)


# ---------------------------------------------------------------------------
# Authentication & download permissions
# ---------------------------------------------------------------------------

class OPDSLoginViewTest(OPDSThrottleResetMixin, TestCase):
    """Tests for GET opds:login — the credential challenge / redirect view."""

    LOGIN_URL = f'{OPDS_BASE}login/'

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='reader', email='reader@example.com', password='pass')

    def test_login_anonymous_returns_401(self):
        """Anonymous GET → 401."""
        response = self.client.get(self.LOGIN_URL)
        self.assertEqual(response.status_code, 401)

    def test_login_anonymous_sets_www_authenticate_basic(self):
        """The 401 response challenges with WWW-Authenticate: Basic."""
        response = self.client.get(self.LOGIN_URL)
        self.assertTrue(
            response['WWW-Authenticate'].startswith('Basic'),
            msg=response.get('WWW-Authenticate'),
        )

    def test_login_authenticated_redirects_to_root(self):
        """Valid Basic creds → 302 redirect to the OPDS root."""
        response = self.client.get(
            self.LOGIN_URL,
            HTTP_AUTHORIZATION=_basic('reader', 'pass'),
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response['Location'].endswith(OPDS_BASE),
            msg=response.get('Location'),
        )

    def test_login_redirect_preserves_detail_thick(self):
        """Valid creds with ?detail=thick → 302 carrying detail=thick to the root."""
        response = self.client.get(
            f'{self.LOGIN_URL}?detail=thick',
            HTTP_AUTHORIZATION=_basic('reader', 'pass'),
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response['Location'].endswith(f'{OPDS_BASE}?detail=thick'),
            msg=response.get('Location'),
        )

    def test_login_invalid_credentials_returns_401(self):
        """A wrong-password Basic header → 401."""
        response = self.client.get(
            self.LOGIN_URL,
            HTTP_AUTHORIZATION=_basic('reader', 'wrong'),
        )
        self.assertEqual(response.status_code, 401)


class OPDSBookDownloadTest(OPDSThrottleResetMixin, BaseTestCase):
    """Tests for GET opds:book_download — the authenticated download endpoint.

    Uses ``BaseTestCase`` so the book can carry a real EPUB file (extracted via
    ``get_book_file_content`` against a temp media root).  ``user_with_perm`` is
    in the ``Book access`` group; ``user_no_perm`` is a plain user.  Basic
    credentials are sent via ``HTTP_AUTHORIZATION`` (session login does not
    authenticate the Basic-only OPDS views).
    """

    @classmethod
    def setUpTestData(cls):
        cls.lang_en = Language.objects.create(code='en', name='English')
        cls.author = Author.objects.create(first_name='John', last_name='Doe')

        cls.book = Book.objects.create(
            title='Test EPUB', language=cls.lang_en, file_type='epub',
        )
        cls.book.authors.add(cls.author)
        cls.book.file.save(
            'test.epub', ContentFile(create_epub_one_author().read())
        )

        # FB2 book stored as an encrypted ZIP; delivered as application/fb2+zip.
        cls.fb2_book = Book.objects.create(
            title='Test FB2', language=cls.lang_en, file_type='fb2',
        )
        cls.fb2_book.authors.add(cls.author)
        cls.fb2_content = create_fb2_one_author().read()
        zip_buffer = io.BytesIO()
        with pyzipper.AESZipFile(
            zip_buffer, 'w',
            compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES,
        ) as zf:
            zf.setpassword(settings.BOOK_PWD)
            zf.writestr('inner.fb2', cls.fb2_content)
        cls.fb2_book.file.save('test.fb2.zip', ContentFile(zip_buffer.getvalue()))

        cls.no_file_book = Book.objects.create(
            title='No File', language=cls.lang_en,
        )

        cls.user_with_perm = User.objects.create_user(
            username='perm', email='perm@example.com', password='pass',
        )
        group, _ = Group.objects.get_or_create(name='Book access')
        cls.user_with_perm.groups.add(group)

        cls.user_no_perm = User.objects.create_user(
            username='plain', email='plain@example.com', password='pass',
        )

    def _download_url(self, book):
        return f'{OPDS_BASE}books/{book.pk}/download/'

    def test_download_anon_returns_401(self):
        """Anonymous download → 401 with WWW-Authenticate: Basic."""
        response = self.client.get(self._download_url(self.book))
        self.assertEqual(response.status_code, 401)
        self.assertTrue(
            response['WWW-Authenticate'].startswith('Basic'),
            msg=response.get('WWW-Authenticate'),
        )

    def test_download_401_has_empty_body(self):
        """The 401 challenge body is empty so readers don't write it to the file.

        Simple OPDS readers persist the challenge body to the download target
        before retrying with credentials; a non-empty body corrupts the saved
        book file.  The WWW-Authenticate header must still be preserved.
        """
        response = self.client.get(self._download_url(self.book))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.content, b'')
        self.assertTrue(response['WWW-Authenticate'].startswith('Basic'))

    def test_download_user_no_perm_returns_403(self):
        """An authenticated user lacking the permission → 403."""
        response = self.client.get(
            self._download_url(self.book),
            HTTP_AUTHORIZATION=_basic('plain', 'pass'),
        )
        self.assertEqual(response.status_code, 403)

    def test_download_403_has_empty_body(self):
        """The 403 (no-permission) response also has an empty body."""
        response = self.client.get(
            self._download_url(self.book),
            HTTP_AUTHORIZATION=_basic('plain', 'pass'),
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content, b'')

    def test_download_user_with_perm_epub_returns_200(self):
        """A permitted user downloads the EPUB → 200 attachment, non-empty body."""
        response = self.client.get(
            self._download_url(self.book),
            HTTP_AUTHORIZATION=_basic('perm', 'pass'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertTrue(response.content)

    def test_download_no_file_returns_404(self):
        """A permitted user requesting a book with no file → 404."""
        response = self.client.get(
            self._download_url(self.no_file_book),
            HTTP_AUTHORIZATION=_basic('perm', 'pass'),
        )
        self.assertEqual(response.status_code, 404)

    def test_download_invalid_pk_returns_404(self):
        """A non-existent book pk → 404, passing through the empty-body override.

        The ``handle_exception`` override only rewrites 401/403; other statuses
        (here a 404 from ``get_object_or_404``) are returned unchanged.
        """
        invalid_pk = Book.objects.order_by('-pk').first().pk + 1000
        response = self.client.get(
            f'{OPDS_BASE}books/{invalid_pk}/download/',
            HTTP_AUTHORIZATION=_basic('perm', 'pass'),
        )
        self.assertEqual(response.status_code, 404)

    def test_download_non_ascii_filename_uses_rfc6266(self):
        """A Cyrillic title yields an RFC 6266 ``filename*=utf-8''`` header."""
        author = Author.objects.create(first_name='Степан', last_name='Бандера')
        book = Book.objects.create(
            title='Москалі', language=self.lang_en, file_type='epub',
        )
        book.authors.add(author)
        book.file.save('test.epub', ContentFile(create_epub_one_author().read()))

        response = self.client.get(
            self._download_url(book),
            HTTP_AUTHORIZATION=_basic('perm', 'pass'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("filename*=utf-8''", response['Content-Disposition'])

    def test_download_fb2_delivered_as_zip(self):
        """An FB2 download is a valid ZIP served as application/fb2+zip.

        The body must be a well-formed archive (central directory present) whose
        single entry holds the original FB2 bytes, and the filename ends ``.zip``.
        """
        response = self.client.get(
            self._download_url(self.fb2_book),
            HTTP_AUTHORIZATION=_basic('perm', 'pass'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/fb2+zip')
        self.assertIn('.fb2.zip"', response['Content-Disposition'])

        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            names = zf.namelist()
            self.assertEqual(len(names), 1)
            self.assertTrue(names[0].endswith('.fb2'))
            self.assertEqual(zf.read(names[0]), self.fb2_content)
