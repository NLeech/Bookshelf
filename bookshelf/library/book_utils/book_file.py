from abc import ABC, abstractmethod
import io
from typing import Any

from PIL.Image import Image
from bs4 import BeautifulSoup


class Chapter:
    """
    Class representing a chapter in a book. Contains:
        the title
        HTML content of the chapter
        list of subchapters
    """

    def __init__(self,
                 title: str,
                 content: str | None = None,
                 level: int = 0,
                 parent: 'Chapter | None' = None,
                 chapter_id: str | None = None):
        self.id = chapter_id
        self.title = title
        self.content = content
        self.subchapters: list['Chapter'] = []
        self.level = level
        self.parent = parent


    @property
    def content_as_text(self) -> str:
        """Returns the chapter content as plain text, or an empty string if content is None."""
        # soup = BeautifulSoup(self.content.decode('utf-8'), 'html.parser')
        if self.content is not None:
            soup = BeautifulSoup(self.content, 'html.parser')
            return soup.get_text()
        return ""


class BookFile(ABC):
    """Abstract base class for book file formats."""

    _registry: dict[str, type['BookFile']] = {}

    @classmethod
    def register_extractor(cls, file_type: str, extractor_cls: type['BookFile']) -> None:
        """Registers an extractor class for a specific file type."""
        cls._registry[file_type] = extractor_cls

    @classmethod
    def get_extractor(cls, file_type: str) -> type['BookFile'] | None:
        """Retrieves the extractor class for a specific file type."""
        return cls._registry.get(file_type)

    def __init__(self) -> None:
        self.book: Any = None  # Placeholder for book object from specific library
        self.authors: list[str] = []
        self.title: str = ''
        self.language: str = ''
        self.description: str = ''
        self.isbn: str = ''
        self.file_type: str = ''
        self.cover: Image | None = None
        self.chapters: list[Chapter] = []

    @abstractmethod
    def load_from_file(self, file_path: str) -> None:
        """
        Load book data from a file.
        :param file_path: Path to the book file.
        """
        pass

    @abstractmethod
    def load_from_stream(self, stream: io.IOBase) -> None:
        """
        Load book data from a stream.
        :param stream:  Input stream containing book data.
        """
        pass

