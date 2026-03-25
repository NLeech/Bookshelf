import io
from typing import List

import ebooklib
from bs4 import BeautifulSoup
from ebooklib.epub import EpubBook, EpubHtml

from .book_file import BookFile, Chapter


class EpubBookFile(BookFile):

    def load_from_file(self, file_path: str) -> None:
        """
        Load EPUB book data from a file.
        :param file_path: Path to the EPUB file.
        """
        self._load_from_source(file_path)

    def load_from_stream(self, stream: io.IOBase) -> None:
        """
        Load EPUB book data from a stream.
        :param stream: A file-like object containing the EPUB data.
        """
        self._load_from_source(stream)

    def _load_from_source(self, source: io.IOBase | str) -> None:
        self.book = ebooklib.epub.read_epub(source)
        self._populate_book_data()

    def _populate_book_data(self) -> None:
        """Extracts metadata and chapters from the loaded EPUB book."""

        metadata_title = self.book.get_metadata('DC', 'title')
        if metadata_title:
            self.title = metadata_title[0][0]

        authors = self.book.get_metadata('DC', 'creator')
        if authors:
            self.authors = [author[0] for author in authors]

        self.chapters = self._get_chapters_from_book()

    def _process_toc_node(self, toc_node, level: int = 0, parent: Chapter = None) -> Chapter:
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

        book_item = self.book.get_item_with_href(link.href)
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

    def _get_chapters_from_book(self) -> List[Chapter]:
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

