import io
import re
import ast
import itertools
import logging
import requests
import gzip
from typing import Generator
from dataclasses import dataclass
from django.db import transaction
from django.conf import settings

from third_part_libraries.models import FlibustaAuthor, FlibustaGenre

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GenreEntry:
    """
    Genre entry in the Flibusta MySQL authors table

    """
    id: int
    genre_code: str
    genre_desc: str
    genre_meta: str

    def __str__(self):
        return f'({self.id}) {self.genre_code}, {self.genre_desc}, {self.genre_meta}'


@dataclass(frozen=True)
class AuthorEntry:
    """
    Author entry in the Flibusta MySQL authors table
    
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


class UpdateError(Exception):
    pass


class FlibustaInterface:
    """
    Interface for the Flibusta library.
    Gets a database dump from the Flibusta site and stores it to the database.

    """

    @staticmethod
    def _get_dump(url: str) -> io.StringIO:
        """
        Get a database dump from the Flibusta site
        :param url: a dump URL
        :return: a raw SQL dump

        """
        response = requests.get(url)

        if response.status_code == 200:
            dump = gzip.decompress(response.content)
            dump = io.StringIO(dump.decode('utf-8'))
            return dump
        else:
            raise UpdateError(f"Error getting dump from {url} "
                              f"response: {response.status_code} "
                              f"reason: {response.reason}")

    @staticmethod
    def _get_entries_from_dump(dump: io.StringIO) -> Generator:
        """
        Generator, returns entry from MySQL backup dump
        :param dump: a MySQL dump
        :return: a dump entry

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
                    yield entry

    @staticmethod
    def _create_author(author_data: AuthorEntry) -> FlibustaAuthor:
        """
        Create an author.
        :param author_data: author's data
        :return: Created author

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

    @classmethod
    def _get_authors_dump(cls) -> io.StringIO:
        """
        Get database dump with authors from Flibusta site
        :return: raw SQL dump

        """
        return cls._get_dump(settings.FLIBUSTA_AUTHORS_URL)

    @classmethod
    def _get_genre_dump(cls) -> io.StringIO:
        """
        Get database dump with genre from Flibusta site
        :return: raw SQL dump

        """
        return cls._get_dump(settings.FLIBUSTA_GENRE_URL)

    def load_authors(self, dump: io.StringIO) -> None:
        """
        Load authors from the Flibusta MySQL authors table dump and store them in the database.
        Existing entries in the database will not be updated.
        :param dump: MySQL dump

        """
        existed_ids = set(FlibustaAuthor.objects.values_list('id', flat=True))

        authors_first_stage = self._get_entries_from_dump(dump)
        authors_first_stage, authors_second_stage = itertools.tee(authors_first_stage)

        # the first pass load only main authors (without master_id)
        with transaction.atomic():
            for entry in authors_first_stage:
                author = AuthorEntry(*entry)
                if author.id in existed_ids:
                    continue

                if not author.master_id:
                    self._create_author(author)

        # the second pass load authors' pseudonyms (entries that have the master_id filled)
        with transaction.atomic():
            for entry in authors_second_stage:
                author = AuthorEntry(*entry)
                if author.id in existed_ids:
                    continue

                if author.master_id:
                    self._create_author(author)

    def load_genre(self, dump: io.StringIO) -> None:
        """
         Load genre from the Flibusta MySQL genre table dump and store them in the database.
         Existing entries in the database will not be updated.
         :param dump: MySQL dump

         """
        genres = self._get_entries_from_dump(dump)
        with transaction.atomic():
            for entry in genres:
                genre = GenreEntry(*entry)
                obj, created = FlibustaGenre.objects.get_or_create(
                    genre_code=genre.genre_code,
                    defaults={
                        'genre_desc': genre.genre_desc,
                        'genre_meta': genre.genre_meta,
                    }
                )
                if created:
                    logger.info(f'Genre created: {obj}')

    def update_genre(self) -> None:
        """
         Get a database dump containing genre from the Flibusta site and store the new genre in the database.

         """
        try:
            dump = self._get_genre_dump()
            self.load_genre(dump)
        except Exception as e:
            logger.error(str(e))

    def update_authors(self) -> None:
        """
        Get a database dump containing authors from the Flibusta site and store the new authors in the database.

        """
        try:
            dump = self._get_authors_dump()
            self.load_authors(dump)
        except Exception as e:
            logger.error(str(e))
