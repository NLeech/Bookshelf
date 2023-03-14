from abc import ABC, abstractmethod
from dataclasses import dataclass
import importlib
from enum import Enum
from typing import BinaryIO
from typing_extensions import Self


# all type of books have to be described here in that format:
# {
#     'file_extension': 'module_name.bookfile_class_name')
# }
# TODO should it moved to settings?
BOOK_FILE_TYPES = {
    'epub': 'epub.EpubFile',
}


@dataclass
class BookFile(ABC):
    """
    Base class for the book file

    """
    book: BinaryIO
    title: str
    description: str
    language: int
    cover: bytes
    isbn: int
    authors: list[str]
    series: list[str]
    genres: list[str]

    @classmethod
    @abstractmethod
    def load_from_file(cls, filename: str) -> Self:
        pass


class BookLoader:
    """
    Loads books to the database

    """
    @staticmethod
    def _get_book_file_class(file_name: str) -> type[BookFile]:
        """
        Returns object for the certain book format depended on filename extension
        :param file_name: full path to file
        :return: appropriate object

        """
        # get file extension
        _, extension = file_name.rsplit('.', 1)

        # get module and class name
        try:
            module_name, class_name = BOOK_FILE_TYPES[extension].rsplit('.', 1)
        except KeyError:
            raise ValueError(f"'{extension}' file type is not supported.")

        return getattr(importlib.import_module(f'.{module_name}', 'library.book_tools'), class_name)

    def load_book_from_file(self, file_name: str) -> BookFile:
        bookfile_class = self._get_book_file_class(file_name)
        return bookfile_class.load_from_file(file_name)




