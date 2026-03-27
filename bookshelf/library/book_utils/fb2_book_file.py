import base64
import io
from typing import List, Optional

from PIL import Image
from bs4 import BeautifulSoup

from .book_file import BookFile, Chapter


class Fb2BookFile(BookFile):
    """
    Class for handling FB2 book files.
    Extracts metadata and chapters from FB2 XML structure.
    """

    def load_from_file(self, file_path: str) -> None:
        """
        Load FB2 book data from a file.
        :param file_path: Path to the FB2 file.
        """
        with open(file_path, 'rb') as f:
            self._load_from_source(f)

    def load_from_stream(self, stream: io.IOBase) -> None:
        """
        Load FB2 book data from a stream.
        :param stream: A file-like object containing the FB2 data.
        """
        self._load_from_source(stream)

    def _load_from_source(self, source: io.IOBase) -> None:
        """
        Internal method to load FB2 data using BeautifulSoup.
        """
        # We use 'xml' parser for FB2
        self.soup = BeautifulSoup(source, 'xml')
        self._populate_book_data()
        pass

    def _populate_book_data(self) -> None:
        """Extracts metadata and chapters from the loaded FB2 book."""
        title_info = self.soup.find('title-info')
        
        if title_info:
            # Title
            title_tag = title_info.find('book-title')
            if title_tag:
                self.title = title_tag.get_text(strip=True)

            # Authors
            author_tags = title_info.find_all('author')
            for auth in author_tags:
                parts = []
                for p in ['first-name', 'middle-name', 'last-name']:
                    t = auth.find(p)
                    if t:
                        parts.append(t.get_text(strip=True))
                
                if parts:
                    self.authors.append(' '.join(parts))
                else:
                    nickname = auth.find('nickname')
                    if nickname:
                        self.authors.append(nickname.get_text(strip=True))

            # Language
            lang_tag = title_info.find('lang')
            if lang_tag:
                self.language = lang_tag.get_text(strip=True)

            # Description (Annotation)
            annotation = title_info.find('annotation')
            if annotation:
                # We store the inner content of annotation as a string
                self.description = "".join([str(c) for c in annotation.contents]).strip()

        self.cover = self._extract_cover()
        self.chapters = self._get_chapters_from_book()

    def _extract_cover(self) -> Optional[Image.Image]:
        """
        Extracts the cover image from the FB2 book.
        :return: PIL Image object if a cover is found, None otherwise.
        """
        coverpage = self.soup.find('coverpage')
        if not coverpage:
            return None
        
        img_tag = coverpage.find('image')
        if not img_tag:
            return None
        
        # href might be l:href or xlink:href
        href = None
        for attr in img_tag.attrs:
            if attr.endswith('href'):
                href = img_tag.attrs[attr]
                break
        
        if not href or not href.startswith('#'):
            return None
        
        binary_id = href[1:]
        # Look for <binary id="ID">
        binary_tag = self.soup.find('binary', id=binary_id)
        if binary_tag and binary_tag.string:
            try:
                img_data = base64.b64decode(binary_tag.string.strip())
                image_stream = io.BytesIO(img_data)
                return Image.open(image_stream)
            except Exception:
                pass
        
        return None

    def _get_chapters_from_book(self) -> List[Chapter]:
        """Extracts chapters from the first <body> element of the FB2 book."""
        body = self.soup.find('body')
        if not body:
            return []
        
        chapters = []
        # Find top-level sections
        sections = body.find_all('section', recursive=False)
        for section in sections:
            chapters.append(self._process_section(section, level=0))
        
        return chapters

    def _process_section(self, section, level: int = 0, parent: Chapter = None) -> Chapter:
        """
        Recursively processes a <section> to create a Chapter object.
        """
        title_tag = section.find('title')
        title = ""
        if title_tag:
            title = title_tag.get_text(strip=True)
        
        # Chapter content is everything except nested sections and the title
        content_parts = []
        for child in section.contents:
            if child.name == 'section':
                continue
            if child.name == 'title':
                continue
            content_parts.append(str(child))
        
        content = "".join(content_parts).strip()
        
        chapter = Chapter(
            title=title or f"Section {level}",
            content=content,
            level=level,
            parent=parent,
            chapter_id=section.get('id')
        )
        
        # Process sub-sections
        subsections = section.find_all('section', recursive=False)
        for sub in subsections:
            chapter.subchapters.append(self._process_section(sub, level + 1, chapter))
            
        return chapter
