import re
import ast
import itertools
import logging
from typing import TextIO, Iterable
from dataclasses import dataclass
from django.db import transaction

from third_part_libraries.models import FlibustaAuthor

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthorEntry:
    """
    Author entry in Flibusta MySQL authors table
    
    """
    id: int
    first_name: str
    middle_name: str
    last_name: str
    nick_name: str
    uid: int
    email: str
    homepage: str
    gender: str
    master_id: int

    def __str__(self):
        return f'({self.id}) {self.last_name}, {self.first_name}, {self.middle_name}'


class FlibustaInterface:
    """
    Interface for the Flibusta library.
    Gets database dump from Flibusta and stores it to the database.

    """

    def _get_authors_dump(self) -> TextIO:
        """
        Get database dump with authors from Flibusta site
        :return: raw SQL dump

        """
        pass

    def _get_authors_from_dump(self, dump: TextIO) -> Iterable:
        """
        Generator, returns entry from MySQL backup dump
        :param dump: MySQL dumps
        :return:
        """
        for line in dump:
            # Split the line into individual SQL statements
            sql_statements = re.split(r';\n+', line)

            for sql in sql_statements:
                # Ignore comments and empty statements
                if sql.startswith('--') or not sql.strip():
                    continue

                # Extract the INSERT INTO statements
                match = re.findall(r".*INSERT INTO.+VALUES\s*(.+)$", sql, re.I | re.M)
                if len(match) == 0:
                    continue

                data = ast.literal_eval('(' + match[0] + ')')

                for entry in data:
                    yield AuthorEntry(*entry)

    def _create_author(self, author_data: AuthorEntry) -> FlibustaAuthor:
        """
        Create author if author with given id didn't find in the database
        :param author_data: author's data
        :return: Found or created author

        """
        main_author = None
        if author_data.master_id:
            try:
                main_author = FlibustaAuthor.objects.get(id=author_data.master_id)
            except FlibustaAuthor.DoesNotExist:
                logger.error(f'Wrong main author id ({author_data.master_id}) for the author: {author_data}')

        author = FlibustaAuthor.objects.create(
            id=author_data.id,
            first_name=author_data.first_name,
            middle_name=author_data.middle_name,
            last_name=author_data.last_name,
            nickname=author_data.nick_name,
            email=author_data.email,
            homepage=author_data.homepage,
            main_author=main_author,
        )

        logger.info(f'Author created: {author}')

        return author

    def load_authors_to_database(self, dump: TextIO) -> None:
        """
        Load authors from Flibusta MySQL authors table dump and store authors to database.
        Existing entries in the database are not updated
        :param dump: MySQL dump

        """
        existed_ids = FlibustaAuthor.objects.values_list('id', flat=True)

        authors_first_stage = self._get_authors_from_dump(dump)
        authors_first_stage, authors_second_stage = itertools.tee(authors_first_stage)

        # the first pass - load only main authors (without master_id)
        with transaction.atomic():
            for author in authors_first_stage:
                if author.id in existed_ids:
                    continue

                if not author.master_id:
                    self._create_author(author)

        # the second pass - load authors' pseudonyms (entries which have master_id filled)
        with transaction.atomic():
            for author in authors_second_stage:
                if author.id in existed_ids:
                    continue

                if author.master_id:
                    self._create_author(author)

        pass

    def load_authors_from_file(self, file_name: str) -> None:
        """

        :param file_name:
        """
        with open(file_name, 'r', encoding="utf8") as file:
            self.load_authors_to_database(file)
