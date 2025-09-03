import io
import os
from unittest.mock import patch, MagicMock

from django.test import TestCase
import gzip

from third_party_libraries.models import FlibustaAuthor, FlibustaGenre
from third_party_libraries.services import FlibustaInterface, AuthorEntry, GenreEntry, UpdateError


class BaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Get the directory containing this test file
        test_dir = os.path.dirname(os.path.abspath(__file__))

        # Build paths to the data files
        authors_file = os.path.join(test_dir, 'avtors_example.txt')
        genre_file = os.path.join(test_dir, 'genrelist_example.txt')

        with open(authors_file, 'r', encoding='utf-8') as f:
            cls.authors_dump = f.read()
        with open(genre_file, 'r', encoding='utf-8') as f:
            cls.genre_dump = f.read()


class GetDumpTest(TestCase):
    @patch('third_party_libraries.services.requests.get')
    def test_get_dump_success(self, mock_get):
        """
        Test that _get_dump successfully decompresses and returns a StringIO object.
        """
        # Create a dummy gzipped content
        content = "test data".encode('utf-8')
        gzipped_content = gzip.compress(content)

        # Configure the mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = gzipped_content
        mock_get.return_value = mock_response

        url = "http://example.com/dump.gz"
        result = FlibustaInterface._get_dump(url)

        mock_get.assert_called_once_with(url)
        self.assertIsInstance(result, io.StringIO)
        self.assertEqual(result.read(), "test data")

    @patch('third_party_libraries.services.requests.get')
    def test_get_dump_failure(self, mock_get):
        """
        Test that _get_dump raises an UpdateError on a non-200 response.
        """
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.reason = "This is a test 404 response: Not Found"
        mock_get.return_value = mock_response

        url = "http://example.com/dump.gz"
        with self.assertRaises(UpdateError):
            FlibustaInterface._get_dump(url)
        mock_get.assert_called_once_with(url)


class GetEntriesFromDumpTest(BaseTestCase):
    def test_get_entries_from_authors_dump(self):
        """
        Test that _get_entries_from_dump correctly parses an authors dump.
        """
        dump_io = io.StringIO(self.authors_dump)
        entries = list(FlibustaInterface._get_entries_from_dump(dump_io))
        self.assertEqual(len(entries), 19)
        self.assertEqual(entries[0][0], 1)
        self.assertEqual(entries[0][3], 'Коллектив авторов')
        # Check for a specific entry's presence instead of relying on order
        self.assertTrue(any(entry[0] == 222 and entry[3] == 'Торн' for entry in entries))

    def test_get_entries_from_genre_dump(self):
        """
        Test that _get_entries_from_dump correctly parses a genre dump.
        """
        dump_io = io.StringIO(self.genre_dump)
        entries = list(FlibustaInterface._get_entries_from_dump(dump_io))
        self.assertEqual(len(entries), 12)
        self.assertEqual(entries[0][0], 1)
        self.assertEqual(entries[0][1], 'sf_history')
        self.assertEqual(entries[11][0], 12)
        self.assertEqual(entries[11][1], 'sf')


class CreateAuthorTest(TestCase):
    def test_create_author_without_master(self):
        """
        Test creating a main author (without a master_id).
        """
        author_data = AuthorEntry(1, 'John', '', 'Doe', 'johndoe', 123, 'j@d.com', 'jd.com', 'm', 0)
        author = FlibustaInterface._create_author(author_data)
        self.assertEqual(FlibustaAuthor.objects.count(), 1)
        self.assertEqual(author.id, 1)
        self.assertEqual(author.first_name, 'John')
        self.assertIsNone(author.main_author)

    def test_create_author_with_master(self):
        """
        Test creating a pseudonym author (with a master_id).
        """
        main_author_data = AuthorEntry(1, 'John', '', 'Doe', 'johndoe', 123, 'j@d.com', 'jd.com', 'm', 0)
        main_author = FlibustaInterface._create_author(main_author_data)

        pseudo_author_data = AuthorEntry(2, 'Jane', '', 'Doe', 'janedoe', 124, 'jane@d.com', 'jane.com', 'f', 1)
        pseudo_author = FlibustaInterface._create_author(pseudo_author_data)

        self.assertEqual(FlibustaAuthor.objects.count(), 2)
        self.assertEqual(pseudo_author.main_author, main_author)

    def test_create_author_with_nonexistent_master(self):
        """
        Test creating an author with a master_id that does not exist.
        """
        author_data = AuthorEntry(1, 'John', '', 'Doe', 'johndoe', 123, 'j@d.com', 'jd.com', 'm', 999)
        author = FlibustaInterface._create_author(author_data)
        self.assertEqual(FlibustaAuthor.objects.count(), 1)
        self.assertIsNone(author.main_author)


class LoadAuthorsTest(BaseTestCase):
    def test_load_authors(self):
        """
        Test that load_authors correctly loads authors and their pseudonyms.
        """
        dump_io = io.StringIO(self.authors_dump)
        interface = FlibustaInterface()
        interface.load_authors(dump_io)

        self.assertEqual(FlibustaAuthor.objects.count(), 19)

        # Test a main author
        author1 = FlibustaAuthor.objects.get(id=8)
        self.assertEqual(author1.first_name, 'Григол')
        self.assertIsNone(author1.main_author)

        # Test a pseudonym
        author2 = FlibustaAuthor.objects.get(id=22)
        self.assertEqual(author2.first_name, 'Кип')
        self.assertIsNotNone(author2.main_author)
        self.assertEqual(author2.main_author.id, 222)

        # Test another main author
        author3 = FlibustaAuthor.objects.get(id=777)
        self.assertEqual(author3.first_name, 'Ричард')
        self.assertIsNone(author3.main_author)

        # Test another pseudonym
        author4 = FlibustaAuthor.objects.get(id=77)
        self.assertEqual(author4.main_author.id, 777)

    def test_load_authors_idempotent(self):
        """
        Test that load_authors does not create duplicate entries.
        """
        dump_io = io.StringIO(self.authors_dump)
        interface = FlibustaInterface()
        interface.load_authors(dump_io)
        self.assertEqual(FlibustaAuthor.objects.count(), 19)

        # Load again
        dump_io.seek(0)
        interface.load_authors(dump_io)
        self.assertEqual(FlibustaAuthor.objects.count(), 19)


class LoadGenreTest(BaseTestCase):
    def test_load_genre(self):
        """
        Test that load_genre correctly loads genres.
        """
        dump_io = io.StringIO(self.genre_dump)
        interface = FlibustaInterface()
        interface.load_genre(dump_io)

        self.assertEqual(FlibustaGenre.objects.count(), 12)
        genre = FlibustaGenre.objects.get(genre_code='sf_history')
        self.assertEqual(genre.genre_desc, 'Альтернативная история')
        self.assertEqual(genre.genre_meta, 'Фантастика')

    def test_load_genre_idempotent(self):
        """
        Test that load_genre does not create duplicate entries.
        """
        dump_io = io.StringIO(self.genre_dump)
        interface = FlibustaInterface()
        interface.load_genre(dump_io)
        self.assertEqual(FlibustaGenre.objects.count(), 12)

        # Load again
        dump_io.seek(0)
        interface.load_genre(dump_io)
        self.assertEqual(FlibustaGenre.objects.count(), 12)


class UpdateGenreTest(BaseTestCase):
    @patch('third_party_libraries.services.FlibustaInterface._get_genre_dump')
    def test_update_genre_success(self, mock_get_dump):
        """
        Test that update_genre calls _get_genre_dump and load_genre.
        """
        dump_io = io.StringIO(self.genre_dump)
        mock_get_dump.return_value = dump_io

        interface = FlibustaInterface()
        interface.update_genre()

        mock_get_dump.assert_called_once()
        self.assertEqual(FlibustaGenre.objects.count(), 12)

    @patch('third_party_libraries.services.FlibustaInterface._get_genre_dump')
    def test_update_genre_exception(self, mock_get_dump):
        """
        Test that update_genre handles exceptions gracefully.
        """
        mock_get_dump.side_effect = Exception("Test exception raising: Genre dump not found")

        interface = FlibustaInterface()
        # We expect the exception to be caught and logged, not raised
        interface.update_genre()

        mock_get_dump.assert_called_once()
        self.assertEqual(FlibustaGenre.objects.count(), 0)


class UpdateAuthorsTest(BaseTestCase):
    @patch('third_party_libraries.services.FlibustaInterface._get_authors_dump')
    def test_update_authors_success(self, mock_get_dump):
        """
        Test that update_authors calls _get_authors_dump and load_authors.
        """
        dump_io = io.StringIO(self.authors_dump)
        mock_get_dump.return_value = dump_io

        interface = FlibustaInterface()
        interface.update_authors()

        mock_get_dump.assert_called_once()
        self.assertEqual(FlibustaAuthor.objects.count(), 19)

    @patch('third_party_libraries.services.FlibustaInterface._get_authors_dump')
    def test_update_authors_exception(self, mock_get_dump):
        """
        Test that update_authors handles exceptions gracefully.
        """
        mock_get_dump.side_effect = Exception("Test exception raising: Authors dump not found")

        interface = FlibustaInterface()
        # We expect the exception to be caught and logged, not raised
        interface.update_authors()

        mock_get_dump.assert_called_once()
        self.assertEqual(FlibustaAuthor.objects.count(), 0)
