"""
OPDS v1.2 catalog tests.

Phase 1 — initial implementation.  Only the root feed endpoint is implemented
and tested in this file.  Subsequent phases will extend this file with tests
for all other OPDS endpoints.
"""
import xml.etree.ElementTree as ET

from django.test import TestCase

NS = {
    'atom': 'http://www.w3.org/2005/Atom',
    'opds': 'http://opds-spec.org/2010/catalog',
    'dc':   'http://purl.org/dc/terms/',
}


def _parse(response):
    """Parse a DRF/Django test response body as an XML element tree."""
    return ET.fromstring(response.content)


class OPDSRootFeedTest(TestCase):
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
