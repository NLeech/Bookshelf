import io
import logging
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote

from PIL import Image
import ebooklib
from bs4 import BeautifulSoup
from bs4.element import Tag
from ebooklib import epub
from ebooklib.epub import EpubHtml, EpubCover, EpubImage, EpubNav

from .book_file import BookFile, Chapter

logger = logging.getLogger(__name__)


@dataclass
class _Boundary:
    """A single chapter boundary in the spine/TOC model.

    A boundary marks where a chapter starts: a ``(spine file, optional #anchor)``
    pair. ``spine_index``/``item`` are ``None`` for pure container nodes (TOC
    sections that group children but resolve to no spine content).

    Attributes:
        chapter: The Chapter produced for this boundary.
        depth: TOC nesting depth (0 == top level), drives tree assembly.
        spine_index: Position of the file in ``book.spine`` (None for containers).
        item: The resolved spine ``EpubHtml`` item (None for containers).
        anchor: The in-file ``#fragment`` for this boundary (None == file start).
        dom_order: Appearance order of ``anchor`` within its file (file start == 0).
    """

    chapter: Chapter
    depth: int
    spine_index: int | None = None
    item: EpubHtml | None = None
    anchor: str | None = None
    dom_order: int = 0


class EpubBookFile(BookFile):

    def load_from_file(self, file_path: str) -> None:
        """Load EPUB book data from a file.

        Args:
            file_path: Path to the EPUB file.
        """
        self._load_from_source(file_path)
        self.size = os.path.getsize(file_path)

    def load_from_stream(self, stream: io.IOBase) -> None:
        """Load EPUB book data from a stream.

        Args:
            stream: A file-like object containing the EPUB data.
        """
        self._load_from_source(stream)

    def _load_from_source(self, source: io.IOBase | str) -> None:
        self.book = ebooklib.epub.read_epub(source)
        self.file_type = 'epub'
        self._populate_book_data()

    def _populate_book_data(self) -> None:
        """Extracts metadata and chapters from the loaded EPUB book."""

        metadata_title = self.book.get_metadata('DC', 'title')
        if metadata_title:
            self.title = metadata_title[0][0]

        authors = self.book.get_metadata('DC', 'creator')
        if authors:
            self.authors = [author[0] for author in authors]

        languages = self.book.get_metadata('DC', 'language')
        if languages and languages[0]:
            self.language = languages[0][0]

        descriptions = self.book.get_metadata('DC', 'description')
        if descriptions and descriptions[0]:
            self.description = descriptions[0][0]

        self.isbn = self._extract_isbn()

        self.cover = self._extract_cover()

        self.chapters = self._get_chapters_from_book()

    def _extract_isbn(self) -> str:
        """Extracts ISBN from EPUB metadata."""
        identifiers = self.book.get_metadata('DC', 'identifier')

        # First pass: look for explicit ISBN scheme or prefix
        for val, attrs in identifiers:
            is_isbn_scheme = False
            if attrs:
                for k, v in attrs.items():
                    # Check for scheme="ISBN", opf:scheme="ISBN", {URI}scheme="ISBN"
                    if (k == 'scheme' or k.endswith('}scheme') or k.endswith(':scheme')) and v.upper() == 'ISBN':
                        is_isbn_scheme = True
                        break

            if is_isbn_scheme:
                return val

            if val and val.lower().startswith('isbn:'):
                return val[5:].strip()

        return ''

    def _extract_cover(self) -> Image.Image | None:
        """Extracts the cover image from the EPUB book.

        Returns:
            PIL Image object if a cover is found, None otherwise.
        """
        # 1. Try to find EpubCover items (EPUB 3.0 standard or marked explicitly)
        for item in self.book.get_items():
            if isinstance(item, EpubCover):
                content = item.get_content()
                if content:
                    try:
                        image_stream = io.BytesIO(content)
                        return Image.open(image_stream)
                    except Exception:
                        pass

        # 2. Try to find cover through metadata (EPUB 2.0 standard)
        # <meta name="cover" content="id123" />

        # We check both None and OPF namespaces
        for ns in [None, 'OPF']:
            try:
                # Some EPUBs have the tag name as 'cover'
                cover_metadata = self.book.get_metadata(ns, 'cover')
                if not cover_metadata:
                    # Others have it as 'meta' with name="cover"
                    all_meta = self.book.get_metadata(ns, 'meta')
                    cover_metadata = [m for m in all_meta if m[1].get('name') == 'cover']
            except (KeyError, IndexError):
                continue

            if cover_metadata:
                for _, attrs in cover_metadata:
                    cover_id = attrs.get('content')
                    if cover_id:
                        item = self.book.get_item_with_id(cover_id)
                        if item:
                            content = item.get_content()
                            if content:
                                try:
                                    image_stream = io.BytesIO(content)
                                    return Image.open(image_stream)
                                except Exception:
                                    pass

        # 3. Fallback: look for items with 'cover' in their ID or filename
        for item in self.book.get_items():
            if isinstance(item, (EpubImage, EpubCover)):
                if 'cover' in (item.id or '').lower() or 'cover' in (item.file_name or '').lower():
                     content = item.get_content()
                     if content:
                        try:
                            image_stream = io.BytesIO(content)
                            return Image.open(image_stream)
                        except Exception:
                            pass

        return None

    # ------------------------------------------------------------------ #
    # TOC normalization helpers
    # ------------------------------------------------------------------ #

    def _normalize_toc(self, toc: Any) -> list:
        """Normalize ``book.toc`` into a flat list of TOC nodes.

        ebooklib uses lists for node collections and a 2-tuple
        ``(Section, [children])`` for a single section node. ``book.toc`` may be a
        list of nodes, a lone ``(Section, [children])`` tuple, a lone ``Link``, or
        ``None``/empty. The discriminator below is the single fix for the
        lone-``Link`` crash and the 2-element-list misfire (a 2-element *list*
        ``[Link, (Section, [...])]`` must NOT be treated as one section node).

        Args:
            toc: The raw ``book.toc`` value.

        Returns:
            A list of TOC nodes (each a ``Link`` or a ``(node, children)`` tuple).
        """
        if not toc:
            return []
        if isinstance(toc, list):
            return toc
        if isinstance(toc, tuple):
            # A lone section node is (Section/Link, children-collection).
            if (len(toc) == 2
                    and isinstance(toc[1], (list, tuple))
                    and isinstance(toc[0], (epub.Link, epub.Section))):
                return [toc]
            return list(toc)
        # Lone Link / Section
        return [toc]

    def _flatten_toc(self, nodes: list, depth: int = 0) -> list[tuple[Any, int, bool]]:
        """Flatten TOC nodes into ``(link, depth, has_children)`` records.

        Walks ``_normalize_toc`` output recursively in pre-order (parent before
        children), carrying TOC nesting depth for later tree assembly.

        Args:
            nodes: A list of TOC nodes.
            depth: Current nesting depth.

        Returns:
            Ordered list of ``(link, depth, has_children)`` tuples.
        """
        flat: list[tuple[Any, int, bool]] = []
        for node in nodes:
            if isinstance(node, tuple):
                link = node[0]
                children = node[1] if len(node) > 1 else []
                flat.append((link, depth, bool(children)))
                flat.extend(self._flatten_toc(list(children), depth + 1))
            else:
                flat.append((node, depth, False))
        return flat

    # ------------------------------------------------------------------ #
    # Generic href / DOM helpers
    # ------------------------------------------------------------------ #

    def _normalize_href(self, href: str | None) -> str:
        """Strip ``#fragment``, percent-decode, and strip a leading ``./``."""
        if not href:
            return ''
        path = href.split('#', 1)[0]
        path = unquote(path)
        if path.startswith('./'):
            path = path[2:]
        return path

    def _fragment(self, href: str | None) -> str | None:
        """Return the ``#fragment`` of an href, or None when absent."""
        if not href:
            return None
        _, _, frag = href.partition('#')
        return frag or None

    def _basename(self, path: str) -> str:
        """Return the final path component."""
        return path.rsplit('/', 1)[-1]

    def _filename(self, item: EpubHtml) -> str:
        """Return a human-friendly filename title for a spine item."""
        base = self._basename(item.get_name() or '')
        stem = os.path.splitext(base)[0]
        return stem or base

    def _parse(self, item: EpubHtml) -> BeautifulSoup:
        """Parse a spine item's HTML into BeautifulSoup."""
        return BeautifulSoup(item.get_content().decode('utf-8', 'ignore'), 'html.parser')

    def _first_heading(self, soup: BeautifulSoup) -> str | None:
        """Return the text of the first ``<h1>..<h6>`` heading, or None."""
        heading = soup.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        if heading:
            text = heading.get_text(strip=True)
            if text:
                return text
        return None

    def _is_empty_content(self, soup: BeautifulSoup) -> bool:
        """Return True when a fragment carries neither real text nor media.

        Non-empty if it has text (over a ~20 char threshold) OR any media node
        (``img``/``svg``/``table``) — an illustration plate legitimately starts a
        chapter with no text.
        """
        if soup.find(['img', 'svg', 'table']):
            return False
        return len(soup.get_text(strip=True)) < 20

    def _body_inner_html(self, item: EpubHtml) -> str:
        """Return the inner HTML of a spine item's ``<body>`` (or whole doc)."""
        soup = self._parse(item)
        if soup.body is not None:
            return soup.body.decode_contents()
        return str(soup)

    def _resolve_spine_item(self, href: str | None) -> EpubHtml | None:
        """Resolve an href to a document item: exact-href then basename fallback.

        A TOC point whose href resolves neither exactly nor by basename is a
        dangling entry (broken/incomplete EPUB); callers skip it. This resolver is
        deliberately NOT broadened beyond exact + basename.
        """
        norm = self._normalize_href(href)
        if not norm:
            return None
        item = self.book.get_item_with_href(norm)
        if isinstance(item, EpubHtml):
            return item
        base = self._basename(norm)
        for candidate in self.book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            if isinstance(candidate, EpubHtml) and self._basename(candidate.get_name() or '') == base:
                return candidate
        return None

    def _spine_content_items(self) -> list[tuple[int, EpubHtml]]:
        """Return ``(spine_index, item)`` for linear, non-nav HTML spine items."""
        items: list[tuple[int, EpubHtml]] = []
        for idx, entry in enumerate(self.book.spine):
            if isinstance(entry, (tuple, list)):
                idref = entry[0]
                linear = entry[1] if len(entry) > 1 else 'yes'
            else:
                idref, linear = entry, 'yes'
            if isinstance(linear, str) and linear.lower() == 'no':
                continue
            item = self.book.get_item_with_id(idref)
            if item is None or not isinstance(item, EpubHtml) or isinstance(item, EpubNav):
                continue
            items.append((idx, item))
        return items

    # ------------------------------------------------------------------ #
    # In-file slicing by DOM anchors
    # ------------------------------------------------------------------ #

    def _child_anchor(self, child: Any, anchor_set: set[str]) -> str | None:
        """Return the TOC fragment that starts a new section at ``child``, if any.

        TOC ``#fragment`` ids sit on block elements (almost always headings) that
        are direct children of ``<body>``. We check the direct child first, then
        any descendant, supporting both ``id=`` and legacy ``<a name=>`` anchors.
        """
        if not isinstance(child, Tag) or not anchor_set:
            return None
        if child.get('id') in anchor_set:
            return child.get('id')
        if child.get('name') in anchor_set:
            return child.get('name')
        for el in child.find_all(True):
            if el.get('id') in anchor_set:
                return el.get('id')
            if el.get('name') in anchor_set:
                return el.get('name')
        return None

    def _slice_file_by_anchors(
        self, item: EpubHtml, anchors: list[str]
    ) -> tuple[dict[str | None, str], list[str | None]]:
        """Slice a file's body into per-anchor HTML fragments.

        Each anchor's content = the anchor's top-level block + following siblings
        up to (not including) the next anchor block, iterating body children in DOM
        order. Body before the first anchor is keyed under ``None`` (the "head"),
        which belongs to the previous chapter / parent container.

        Args:
            item: The spine item to slice.
            anchors: TOC fragments targeting this file.

        Returns:
            A ``(content_by_anchor, dom_order)`` pair. ``content_by_anchor`` maps
            each found fragment (and ``None`` for the head) to an HTML string;
            ``dom_order`` lists ``None`` followed by fragments in DOM appearance
            order.
        """
        soup = self._parse(item)
        body = soup.body if soup.body is not None else soup
        anchor_set = set(anchors)

        buckets: dict[str | None, list[str]] = {None: []}
        order: list[str | None] = [None]
        current: str | None = None
        for child in body.children:
            frag = self._child_anchor(child, anchor_set)
            if frag is not None:
                current = frag
                if frag not in buckets:
                    buckets[frag] = []
                    order.append(frag)
            buckets.setdefault(current, [])
            buckets[current].append(str(child))

        for frag in anchors:
            if frag not in buckets:
                # Anchor with no matching DOM element: treat the file as if it had
                # no anchor there; its content stays with the head/previous chapter.
                logger.debug('TOC anchor #%s not found in %s', frag, item.get_name())

        return {key: ''.join(parts) for key, parts in buckets.items()}, order

    # ------------------------------------------------------------------ #
    # Chapter orchestration
    # ------------------------------------------------------------------ #

    def _toc_title(self, link: Any, item: EpubHtml | None) -> str:
        """Resolve a TOC chapter title: TOC title -> first heading -> filename."""
        title = (getattr(link, 'title', '') or '').strip()
        if title:
            return title
        if item is not None:
            heading = self._first_heading(self._parse(item))
            if heading:
                return heading
            return self._filename(item)
        return ''

    def _chapters_without_toc(self, spine_items: list[tuple[int, EpubHtml]]) -> list[Chapter]:
        """NO-TOC fallback: each non-empty spine content file is one flat chapter.

        Title precedence is first heading -> filename (no "Предисловие" fallback,
        unlike pre-TOC front matter).
        """
        chapters: list[Chapter] = []
        for _, item in spine_items:
            soup = self._parse(item)
            if self._is_empty_content(soup):
                continue
            title = self._first_heading(soup) or self._filename(item)
            chapters.append(
                Chapter(
                    title=title,
                    content=self._body_inner_html(item),
                    level=0,
                    chapter_id=item.id,
                )
            )
        return chapters

    def _fill_contents(
        self,
        content_order: list[_Boundary],
        slices: dict[str, tuple[dict[str | None, str], list[str | None]]],
        spine_by_index: dict[int, EpubHtml],
        num_spine: int,
    ) -> None:
        """Assign content to each boundary in spine order.

        A chapter's content runs from its boundary up to the next boundary in
        spine order: its own anchor slice, plus whole gap files with no TOC point
        of their own, plus the head of the next file before its first anchor (which
        belongs to this — the previous — chapter). Calibre split tails and gap
        files fold in for free under this model.
        """
        total = len(content_order)
        for i, boundary in enumerate(content_order):
            nxt = content_order[i + 1] if i + 1 < total else None
            parts = [self._own_content(boundary, slices)]

            end = nxt.spine_index if nxt is not None else num_spine
            for k in range(boundary.spine_index + 1, end):
                gap_item = spine_by_index.get(k)
                if gap_item is not None:
                    parts.append(self._body_inner_html(gap_item))

            if (nxt is not None
                    and nxt.spine_index != boundary.spine_index
                    and nxt.anchor is not None):
                parts.append(self._head_content(nxt, slices))

            boundary.chapter.content = ''.join(part for part in parts if part)

    def _own_content(
        self,
        boundary: _Boundary,
        slices: dict[str, tuple[dict[str | None, str], list[str | None]]],
    ) -> str:
        """Return the boundary's own in-file slice (head when anchor is None)."""
        if boundary.item is None:
            return ''
        sliced = slices.get(boundary.item.id)
        if sliced is None:
            return self._body_inner_html(boundary.item)
        content_by_anchor, _ = sliced
        return content_by_anchor.get(boundary.anchor, '')

    def _head_content(
        self,
        boundary: _Boundary,
        slices: dict[str, tuple[dict[str | None, str], list[str | None]]],
    ) -> str:
        """Return the head (pre-first-anchor) HTML of a boundary's file."""
        if boundary.item is None:
            return ''
        sliced = slices.get(boundary.item.id)
        if sliced is None:
            return ''
        content_by_anchor, _ = sliced
        return content_by_anchor.get(None, '')

    def _assemble_tree(self, tree_order: list[_Boundary]) -> list[Chapter]:
        """Build the parent/child tree purely from TOC depth.

        Independent of how content was sliced (handles interleaved levels within a
        single file): a running stack nests each chapter under the closest shallower
        ancestor.
        """
        roots: list[Chapter] = []
        stack: list[_Boundary] = []
        for boundary in tree_order:
            while stack and stack[-1].depth >= boundary.depth:
                stack.pop()
            boundary.chapter.level = boundary.depth
            if stack:
                stack[-1].chapter.subchapters.append(boundary.chapter)
            else:
                roots.append(boundary.chapter)
            stack.append(boundary)
        return roots

    def _get_chapters_from_book(self) -> list[Chapter]:
        """Extract chapters using the "TOC defines boundaries, spine fills" model.

        A chapter spans spine content from one TOC navigation point up to the next,
        in spine order; a boundary is a ``(spine file, optional #anchor)`` pair.
        Content slicing (DOM order of anchors) and tree building (TOC nesting) are
        independent.
        """
        spine_items = self._spine_content_items()
        spine_by_index = {idx: item for idx, item in spine_items}
        item_index = {item.id: idx for idx, item in spine_items}
        num_spine = len(self.book.spine)

        flat = self._flatten_toc(self._normalize_toc(self.book.toc))
        if not flat:
            return self._chapters_without_toc(spine_items)

        # Resolve TOC links and group fragments per file.
        resolved: list[tuple[Any, int, bool, EpubHtml | None, str | None]] = []
        file_frags: dict[str, list[str]] = {}
        for link, depth, has_children in flat:
            href = getattr(link, 'href', '') or ''
            item = self._resolve_spine_item(href)
            frag = self._fragment(href)
            if item is not None and item.id in item_index:
                resolved.append((link, depth, has_children, item, frag))
                if frag is not None:
                    bucket = file_frags.setdefault(item.id, [])
                    if frag not in bucket:
                        bucket.append(frag)
            else:
                resolved.append((link, depth, has_children, None, None))

        # Slice every referenced file once (in DOM order).
        slices: dict[str, tuple[dict[str | None, str], list[str | None]]] = {}
        for _, _, _, item, _ in resolved:
            if item is not None and item.id not in slices:
                slices[item.id] = self._slice_file_by_anchors(item, file_frags.get(item.id, []))

        # Build TOC boundaries in flatten (tree) order.
        toc_boundaries: list[_Boundary] = []
        for link, depth, has_children, item, frag in resolved:
            title = self._toc_title(link, item)
            if item is None:
                if has_children:
                    # Container node (e.g. a part heading) that resolves to no
                    # spine content: keep it so its children nest correctly.
                    container = Chapter(
                        title=title,
                        content='',
                        level=depth,
                        chapter_id=getattr(link, 'href', None),
                    )
                    toc_boundaries.append(_Boundary(chapter=container, depth=depth))
                else:
                    logger.debug('Skipping dangling TOC entry: %r', getattr(link, 'href', None))
                continue

            _, order = slices[item.id]
            if frag is None:
                dom_order = 0
            elif frag in order:
                dom_order = order.index(frag)
            else:
                dom_order = len(order)
            chapter = Chapter(
                title=title,
                content='',
                level=depth,
                chapter_id=getattr(link, 'href', None),
            )
            toc_boundaries.append(
                _Boundary(
                    chapter=chapter,
                    depth=depth,
                    spine_index=item_index[item.id],
                    item=item,
                    anchor=frag,
                    dom_order=dom_order,
                )
            )

        content_toc = [b for b in toc_boundaries if b.spine_index is not None]

        # Pre-TOC front matter: spine files before the first TOC boundary.
        pre_toc: list[_Boundary] = []
        if content_toc:
            first_index = min(b.spine_index for b in content_toc)
            for idx, item in spine_items:
                if idx >= first_index:
                    break
                soup = self._parse(item)
                if self._is_empty_content(soup):
                    continue
                title = self._first_heading(soup) or self._filename(item) or 'Предисловие'
                chapter = Chapter(title=title, content='', level=0, chapter_id=item.id)
                pre_toc.append(
                    _Boundary(chapter=chapter, depth=0, spine_index=idx, item=item, anchor=None)
                )

        tree_order = pre_toc + toc_boundaries
        content_order = sorted(
            pre_toc + content_toc, key=lambda b: (b.spine_index, b.dom_order)
        )

        self._fill_contents(content_order, slices, spine_by_index, num_spine)

        return self._assemble_tree(tree_order)


BookFile.register_extractor('epub', EpubBookFile)
