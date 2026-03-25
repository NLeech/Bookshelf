import io
from typing import List, Optional
import xml.etree.ElementTree as ET

from .book_file import BookFile


class Fb2BookFile(BookFile):

    def _parse_authors(self, root: ET.Element) -> List[str]:
        """Parse authors from FB2 XML.

        Args:
            root: The XML root element of the FB2 file

        Returns:
            List of author names in "FirstName LastName" format
        """
        authors = []
        # Namespace handling for FB2
        ns = {'fb': 'http://www.gribuser.ru/xml/fictionbook/2.0'}

        # Find all author elements in title-info section
        title_info = root.find('.//fb:description/fb:title-info', ns)
        if title_info is not None:
            for author_elem in title_info.findall('fb:author', ns):
                first_name = author_elem.find('fb:first-name', ns)
                last_name = author_elem.find('fb:last-name', ns)

                # Build author name
                name_parts = []
                if first_name is not None and first_name.text:
                    name_parts.append(first_name.text.strip())
                if last_name is not None and last_name.text:
                    name_parts.append(last_name.text.strip())

                if name_parts:
                    authors.append(' '.join(name_parts))

        return authors

    def _parse_title(self, root: ET.Element) -> str:
        """Parse book title from FB2 XML.

        Args:
            root: The XML root element of the FB2 file

        Returns:
            Book title as string
        """
        # Namespace handling for FB2
        ns = {'fb': 'http://www.gribuser.ru/xml/fictionbook/2.0'}

        # Find book-title in title-info section
        title_info = root.find('.//fb:description/fb:title-info', ns)
        if title_info is not None:
            title_elem = title_info.find('fb:book-title', ns)
            if title_elem is not None and title_elem.text:
                return title_elem.text.strip()

        return ""

    def load_from_file(self, file_path: str) -> None:
        """Load FB2 book data from a file."""
        tree = ET.parse(file_path)
        root = tree.getroot()

        self.authors = self._parse_authors(root)
        self.title = self._parse_title(root)

    def load_from_stream(self, stream: io.IOBase) -> None:
        """Load FB2 book data from a stream. """
        tree = ET.parse(stream)
        root = tree.getroot()

        self.authors = self._parse_authors(root)
        self.title = self._parse_title(root)
