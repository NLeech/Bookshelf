from typing_extensions import Self
from ebooklib import epub

from .book_tools import BookFile


class EpubFile(BookFile):

    @classmethod
    def load_from_file(cls, filename: str) -> Self:
        book = epub.read_epub(filename)
        pass


