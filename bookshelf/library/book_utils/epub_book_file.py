import io
import os
from typing import Any

from PIL import Image
import ebooklib
from bs4 import BeautifulSoup
from ebooklib.epub import EpubBook, EpubHtml, EpubCover, EpubImage

from .book_file import BookFile, Chapter


class EpubBookFile(BookFile):

    def load_from_file(self, file_path: str) -> None:
        """
        Load EPUB book data from a file.
        :param file_path: Path to the EPUB file.
        """
        self._load_from_source(file_path)
        self.size = os.path.getsize(file_path)

    def load_from_stream(self, stream: io.IOBase) -> None:
        """
        Load EPUB book data from a stream.
        :param stream: A file-like object containing the EPUB data.
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
        
        :return: PIL Image object if a cover is found, None otherwise.
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

    def _process_toc_node(self, toc_node: Any, level: int = 0, parent: Chapter | None = None) -> Chapter:
        """
        Recursively processes a TOC node to create a Chapter object, including its subchapters.
        :param toc_node: A node from the EPUB table of contents, which can be a tuple (link, children) or a single link.
        :param level:  The depth level of the chapter in the hierarchy (0 for top-level chapters).
        :param parent: The parent Chapter object, or None if this is a top-level chapter.
        :return: A Chapter object representing the current TOC node and its subchapters.
        """

        if isinstance(toc_node, tuple):
            link, children = toc_node
        else:
            link, children = toc_node, []

        # Strip the anchor to get the actual file path
        file_path = link.href.split('#')[0]
        book_item = self.book.get_item_with_href(file_path)
        content_html = ''
        if book_item:
            content_bytes = book_item.get_content()
            content_html = content_bytes.decode('utf-8', 'ignore')

        soup = BeautifulSoup(content_html, 'html.parser')
        title_tag = soup.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        title = title_tag.get_text(strip=True) if title_tag else link.title

        chapter = Chapter(
            chapter_id=link.href,
            title=title,
            content=content_html,
            level=level,
            parent=parent
        )

        for child_node in children:
            chapter.subchapters.append(
                self._process_toc_node(child_node, level + 1, chapter)
            )

        return chapter

    def _get_chapters_from_book(self) -> list[Chapter]:
        """Extracts chapters from the EPUB book using the table of contents (TOC)."""

        chapters = []
        toc = self.book.toc

        if toc:
            for toc_node in toc:
                chapters.append(self._process_toc_node(toc_node,  0, None))
        else:
            # Fallback to spine if TOC is not available
            for item_id, _ in self.book.spine:
                item = self.book.get_item_with_id(item_id)
                if item and isinstance(item, EpubHtml) and item.is_chapter():
                    content_bytes = item.get_content()
                    content_html = content_bytes.decode('utf-8', 'ignore')
                    soup = BeautifulSoup(content_html, 'html.parser')
                    title_tag = soup.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                    title = title_tag.get_text(strip=True) if title_tag else item.get_name()
                    chapters.append(Chapter(title=title, content=content_html, chapter_id=item.id))

        return chapters


BookFile.register_extractor('epub', EpubBookFile)

