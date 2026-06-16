import xml.etree.ElementTree as ET

from rest_framework.renderers import BaseRenderer

ATOM_NS = 'http://www.w3.org/2005/Atom'
OPDS_NS = 'http://opds-spec.org/2010/catalog'
DC_NS = 'http://purl.org/dc/terms/'
OPENSEARCH_NS = 'http://a9.com/-/spec/opensearch/1.1/'

# Register namespaces at module import time to suppress ns0:, ns1: etc. prefixes.
ET.register_namespace('', ATOM_NS)
ET.register_namespace('opds', OPDS_NS)
ET.register_namespace('dc', DC_NS)
ET.register_namespace('opensearch', OPENSEARCH_NS)

NAV_CONTENT_TYPE = 'application/atom+xml;profile=opds-catalog;kind=navigation'
ACQ_CONTENT_TYPE = 'application/atom+xml;profile=opds-catalog;kind=acquisition'


def _fmt_datetime(dt) -> str:
    """Format a datetime as an RFC 3339 / ISO 8601 string in UTC."""
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


class OPDSRenderer(BaseRenderer):
    media_type = 'application/atom+xml'
    format = 'atom'
    charset = 'utf-8'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if data is None:
            return b''

        # Override Content-Type based on feed kind ('navigation' or 'acquisition').
        if renderer_context and renderer_context.get('response') is not None:
            kind = data.get('kind', 'navigation')
            content_type = NAV_CONTENT_TYPE if kind == 'navigation' else ACQ_CONTENT_TYPE
            renderer_context['response']['Content-Type'] = f'{content_type}; charset=utf-8'

        feed_el = self._build_feed(data)
        ET.indent(feed_el, space='  ')
        xml_bytes = ET.tostring(feed_el, encoding='unicode').encode('utf-8')
        return b'<?xml version="1.0" encoding="utf-8"?>\n' + xml_bytes

    def _build_feed(self, data: dict) -> ET.Element:
        feed = ET.Element(f'{{{ATOM_NS}}}feed')

        ET.SubElement(feed, f'{{{ATOM_NS}}}id').text = data.get('id', '')
        ET.SubElement(feed, f'{{{ATOM_NS}}}title').text = data.get('title', '')

        updated = data.get('updated')
        if updated is not None:
            ET.SubElement(feed, f'{{{ATOM_NS}}}updated').text = _fmt_datetime(updated)

        # Determine the content type for self/next/prev links based on feed kind.
        kind = data.get('kind', 'navigation')
        feed_type = NAV_CONTENT_TYPE if kind == 'navigation' else ACQ_CONTENT_TYPE

        self_link = data.get('self_link')
        if self_link:
            el = ET.SubElement(feed, f'{{{ATOM_NS}}}link')
            el.set('rel', 'self')
            el.set('href', self_link)
            el.set('type', feed_type)

        start_link = data.get('start_link')
        if start_link:
            el = ET.SubElement(feed, f'{{{ATOM_NS}}}link')
            el.set('rel', 'start')
            el.set('href', start_link)
            el.set('type', NAV_CONTENT_TYPE)

        # Pagination links.
        pagination = data.get('pagination')
        if pagination:
            for rel in ('first', 'next', 'previous'):
                href = pagination.get(rel)
                if href:
                    el = ET.SubElement(feed, f'{{{ATOM_NS}}}link')
                    el.set('rel', rel)
                    el.set('href', href)
                    el.set('type', feed_type)

        for entry_data in data.get('entries', []):
            feed.append(self._build_entry(entry_data))

        return feed

    def _build_entry(self, entry: dict) -> ET.Element:
        el = ET.Element(f'{{{ATOM_NS}}}entry')

        ET.SubElement(el, f'{{{ATOM_NS}}}title').text = entry.get('title', '')
        ET.SubElement(el, f'{{{ATOM_NS}}}id').text = entry.get('id', '')

        updated = entry.get('updated')
        if updated is not None:
            ET.SubElement(el, f'{{{ATOM_NS}}}updated').text = _fmt_datetime(updated)

        content = entry.get('content')
        if content is not None:
            content_el = ET.SubElement(el, f'{{{ATOM_NS}}}content')
            content_el.set('type', 'text')
            content_el.text = str(content)

        summary = entry.get('summary')
        if summary:
            ET.SubElement(el, f'{{{ATOM_NS}}}summary').text = summary

        # Author elements — present on book (acquisition) entries only.
        for author in entry.get('authors', []):
            author_el = ET.SubElement(el, f'{{{ATOM_NS}}}author')
            ET.SubElement(author_el, f'{{{ATOM_NS}}}name').text = author.get('name', '')
            uri = author.get('uri')
            if uri:
                ET.SubElement(author_el, f'{{{ATOM_NS}}}uri').text = uri

        # Link elements.
        for link in entry.get('links', []):
            link_el = ET.SubElement(el, f'{{{ATOM_NS}}}link')
            link_el.set('rel', link.get('rel', ''))
            link_el.set('href', link.get('href', ''))
            link_type = link.get('type')
            if link_type:
                link_el.set('type', link_type)
            link_title = link.get('title')
            if link_title:
                link_el.set('title', link_title)

        return el


class OpenSearchRenderer(BaseRenderer):
    media_type = 'application/opensearchdescription+xml'
    format = 'opensearch'
    charset = 'utf-8'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if data is None:
            return b''

        ns = OPENSEARCH_NS
        root = ET.Element(f'{{{ns}}}OpenSearchDescription')

        ET.SubElement(root, f'{{{ns}}}ShortName').text = data.get('short_name', '')
        ET.SubElement(root, f'{{{ns}}}Description').text = data.get('description', '')

        url_el = ET.SubElement(root, f'{{{ns}}}Url')
        url_el.set('type', 'application/atom+xml')
        url_el.set('template', data.get('template', ''))

        ET.SubElement(root, f'{{{ns}}}Language').text = data.get('language', '*')
        ET.SubElement(root, f'{{{ns}}}OutputEncoding').text = 'UTF-8'
        ET.SubElement(root, f'{{{ns}}}InputEncoding').text = 'UTF-8'

        ET.indent(root, space='  ')
        xml_bytes = ET.tostring(root, encoding='unicode').encode('utf-8')
        return b'<?xml version="1.0" encoding="UTF-8"?>\n' + xml_bytes
