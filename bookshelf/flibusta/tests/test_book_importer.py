from django.test import TestCase
from unittest.mock import patch, MagicMock, call
import io
import os
import zipfile
import pyzipper
import shutil
import tempfile
from django.core.files import File
from django.conf import settings
from django.test import override_settings

from flibusta.book_importer import (
    BookImporter, LanguageFilter, FormatFilter, GenreFilter,
    get_daily_links, get_filters, process_archive, process_daily_updates,
    process_local_path
)
from flibusta.models import (
    FlibustaBook, FlibustaAuthor, FlibustaGenre, FlibustaSequence,
    FlibustaBookSequence, FlibustaBookMapping
)
from library.models import Author, Genre, Book, Language, BookSeries, BookSeriesLink


class TestBookFilters(TestCase):
    def setUp(self):
        self.genre_sf = FlibustaGenre.objects.create(genre_code='sf', genre_desc='Sci-Fi', genre_meta='Fiction')
        self.book_ru = FlibustaBook.objects.create(id=1, title='Book RU', lang='ru', file_type='fb2', md5='md5_1')
        self.book_en = FlibustaBook.objects.create(id=2, title='Book EN', lang='en', file_type='epub', md5='md5_2')
        self.book_ru.genres.add(self.genre_sf)

    def test_language_filter(self):
        filter_ru = LanguageFilter(['ru'])
        qs = filter_ru.apply(FlibustaBook.objects.all())
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().lang, 'ru')

        filter_multi = LanguageFilter(['ru', 'en'])
        qs = filter_multi.apply(FlibustaBook.objects.all())
        self.assertEqual(qs.count(), 2)

        filter_empty = LanguageFilter([])
        qs = filter_empty.apply(FlibustaBook.objects.all())
        self.assertEqual(qs.count(), 2)

    def test_format_filter(self):
        filter_fb2 = FormatFilter(['fb2'])
        qs = filter_fb2.apply(FlibustaBook.objects.all())
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().file_type, 'fb2')

        filter_empty = FormatFilter([])
        qs = filter_empty.apply(FlibustaBook.objects.all())
        self.assertEqual(qs.count(), 2)

    def test_genre_filter(self):
        filter_sf = GenreFilter(['sf'])
        qs = filter_sf.apply(FlibustaBook.objects.all())
        self.assertEqual(qs.count(), 1)

        filter_meta = GenreFilter(['Fiction'])
        qs = filter_meta.apply(FlibustaBook.objects.all())
        self.assertEqual(qs.count(), 1)

        filter_none = GenreFilter(['nonexistent'])
        qs = filter_none.apply(FlibustaBook.objects.all())
        self.assertEqual(qs.count(), 0)


# Create a temporary directory for media files
temp_media_root = tempfile.mkdtemp()

@override_settings(MEDIA_ROOT=temp_media_root)
class TestBookImporterService(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(temp_media_root, ignore_errors=True)

    def setUp(self):
        self.importer = BookImporter()
        self.lang_ru = Language.objects.create(code='ru', name='Russian')

    def test_get_language(self):
        self.assertEqual(self.importer.get_language('ru'), self.lang_ru)
        with self.assertLogs('flibusta.book_importer', level='ERROR') as cm:
            self.assertIsNone(self.importer.get_language('en'))
        self.assertTrue(any("Language with code 'en' not found" in output for output in cm.output))

    def test_get_or_create_genre(self):
        f_genre = FlibustaGenre.objects.create(genre_code='sf_action', genre_desc='Action SF', genre_meta='sf')
        
        # First call - creates Genre and Meta Genre
        l_genre = self.importer.get_or_create_genre(f_genre)
        self.assertEqual(l_genre.code, 'sf_action')
        self.assertEqual(l_genre.parent.code, 'sf')
        self.assertTrue(hasattr(f_genre, 'mapping'))
        
        # Second call - uses mapping
        l_genre_2 = self.importer.get_or_create_genre(f_genre)
        self.assertEqual(l_genre, l_genre_2)
        self.assertEqual(Genre.objects.count(), 2) # sf and sf_action

    def test_get_or_create_author_with_master(self):
        master = FlibustaAuthor.objects.create(id=10, last_name='Master', first_name='M')
        alias = FlibustaAuthor.objects.create(id=11, last_name='Alias', first_name='A', master_id=10)
        
        l_author = self.importer.get_or_create_author(alias)
        self.assertEqual(l_author.last_name, 'Master')
        
        # Verify mappings
        self.assertEqual(alias.mapping.library_author, l_author)
        self.assertEqual(master.mapping.library_author, l_author)
        self.assertEqual(Author.objects.count(), 1)

    def test_get_or_create_author_with_missing_master(self):
        alias = FlibustaAuthor.objects.create(id=11, last_name='Alias', first_name='A', master_id=99)
        # Master with id=99 does not exist
        
        with self.assertLogs('flibusta.book_importer', level='ERROR') as cm:
            l_author = self.importer.get_or_create_author(alias)
            
        self.assertEqual(l_author.last_name, 'Alias')
        self.assertTrue(any("Master author 99 for 11 not found" in output for output in cm.output))
        self.assertEqual(Author.objects.count(), 1)

    def test_get_or_create_series_basic(self):
        f_seq = FlibustaSequence.objects.create(id=1, name='Test Series')
        
        # First call
        l_series = self.importer.get_or_create_series(f_seq)
        self.assertEqual(l_series.name, 'Test Series')
        
        # Second call - uses mapping
        l_series_2 = self.importer.get_or_create_series(f_seq)
        self.assertEqual(l_series, l_series_2)
        self.assertEqual(BookSeries.objects.count(), 1)

    @patch('pyzipper.AESZipFile')
    def test_import_book_no_language(self, mock_zip):
        f_book = FlibustaBook.objects.create(id=101, title='No Lang', lang='en', file_type='fb2', md5='md5_101')
        # Language 'en' not created in setUp
        
        self.importer.import_book(f_book, b'content')
        self.assertFalse(Book.objects.filter(title='No Lang').exists())

    @patch('pyzipper.AESZipFile')
    def test_import_book_success(self, mock_zip):
        f_author = FlibustaAuthor.objects.create(id=1, last_name='Author')
        f_genre = FlibustaGenre.objects.create(genre_code='sf', genre_desc='SF', genre_meta='sf')
        f_seq = FlibustaSequence.objects.create(id=1, name='Series')
        f_book = FlibustaBook.objects.create(id=100, title='Test Book', lang='ru', file_type='fb2', md5='md5_100')
        f_book.authors.add(f_author)
        f_book.genres.add(f_genre)
        FlibustaBookSequence.objects.create(book=f_book, sequence=f_seq, seq_numb=1)

        # Mock Zip context manager
        mock_zf = MagicMock()
        mock_zip.return_value.__enter__.return_value = mock_zf

        self.importer.import_book(f_book, b'content')

        # Verify Book
        book = Book.objects.get(title='Test Book')
        self.assertEqual(book.language, self.lang_ru)
        self.assertTrue(book.file.name.endswith('100.zip'), f"Expected name to end with 100.zip, got {book.file.name}")
        
        # Verify relations
        self.assertTrue(book.authors.filter(last_name='Author').exists())
        self.assertTrue(book.genres.filter(code='sf').exists())
        self.assertTrue(BookSeriesLink.objects.filter(book=book, series__name='Series', sequence_number=1).exists())
        
        # Verify mapping
        self.assertTrue(FlibustaBookMapping.objects.filter(flibusta_book=f_book, library_book=book).exists())


class TestArchiveProcessing(TestCase):
    @patch('flibusta.book_importer.zipfile.is_zipfile')
    @patch('flibusta.book_importer.zipfile.ZipFile')
    @patch('flibusta.book_importer.BookImporter.import_book')
    def test_process_archive_basic(self, mock_import, mock_zip_class, mock_is_zip):
        mock_is_zip.return_value = True
        f_book = FlibustaBook.objects.create(id=100, title='Test', lang='ru', file_type='fb2', md5='md5_100')
        
        mock_zip_instance = MagicMock()
        mock_zip_instance.namelist.return_value = ['100.fb2']
        mock_zip_instance.open.return_value.__enter__.return_value = io.BytesIO(b'content')
        mock_zip_class.return_value.__enter__.return_value = mock_zip_instance
        
        process_archive('dummy.zip', [])
            
        mock_import.assert_called_once_with(f_book, b'content')

    @patch('flibusta.book_importer.zipfile.is_zipfile')
    @patch('flibusta.book_importer.zipfile.ZipFile')
    @patch('flibusta.book_importer.BookImporter.import_book')
    def test_process_archive_skip_imported_and_deleted(self, mock_import, mock_zip_class, mock_is_zip):
        mock_is_zip.return_value = True
        f_imported = FlibustaBook.objects.create(id=100, title='Imported', lang='ru', file_type='fb2', md5='md5_100')
        l_book = Book.objects.create(title='Imported', language=Language.objects.create(code='ru'))
        FlibustaBookMapping.objects.create(flibusta_book=f_imported, library_book=l_book)
        
        f_deleted = FlibustaBook.objects.create(id=101, title='Deleted', lang='ru', file_type='fb2', deleted='1', md5='md5_101')
        
        mock_zip_instance = MagicMock()
        mock_zip_instance.namelist.return_value = ['100.fb2', '101.fb2']
        mock_zip_class.return_value.__enter__.return_value = mock_zip_instance
        
        process_archive('dummy.zip', [])
            
        mock_import.assert_not_called()

    @patch('flibusta.book_importer.zipfile.is_zipfile')
    @patch('flibusta.book_importer.zipfile.ZipFile')
    @patch('flibusta.book_importer.BookImporter.import_book')
    def test_process_archive_nested(self, mock_import, mock_zip_class, mock_is_zip):
        mock_is_zip.return_value = True
        f_book = FlibustaBook.objects.create(id=100, title='Test', lang='ru', file_type='fb2', md5='md5_100')
        
        # Outer zip instance
        mock_outer_zip = MagicMock()
        mock_outer_zip.namelist.return_value = ['100.fb2.zip']
        mock_outer_zip.open.return_value.__enter__.return_value = io.BytesIO(b'nested_zip_content')
        
        # Inner zip instance
        mock_inner_zip = MagicMock()
        mock_inner_zip.namelist.return_value = ['book.fb2']
        mock_inner_zip.read.return_value = b'actual content'
        
        mock_zip_class.side_effect = [
            MagicMock(__enter__=MagicMock(return_value=mock_outer_zip)),
            MagicMock(__enter__=MagicMock(return_value=mock_inner_zip))
        ]
        
        process_archive('dummy.zip', [])
            
        mock_import.assert_called_once_with(f_book, b'actual content')


class TestUtilityFunctions(TestCase):
    def test_get_daily_links(self):
        html = """
        <a href="f.fb2.123-456.zip">link1</a>
        <a href="https://other.com/f.n.789-000.zip">link2</a>
        """
        links = get_daily_links(html)
        self.assertEqual(len(links), 2)
        self.assertEqual(links[0]['filename'], 'f.fb2.123-456.zip')
        self.assertTrue(links[0]['url'].endswith('/daily/f.fb2.123-456.zip'))
        self.assertEqual(links[1]['url'], 'https://other.com/f.n.789-000.zip')

    def test_get_filters(self):
        filters = get_filters(genres_filters=['sf'], formats_filters=['fb2'], languages_filters=['ru'])
        self.assertEqual(len(filters), 3)
        self.assertIsInstance(filters[0], GenreFilter)
        self.assertIsInstance(filters[1], FormatFilter)
        self.assertIsInstance(filters[2], LanguageFilter)

    @patch('flibusta.book_importer.requests.get')
    def test_download_file(self, mock_get):
        from flibusta.book_importer import download_file
        mock_response = MagicMock()
        mock_response.iter_content.return_value = [b'chunk1', b'chunk2']
        mock_get.return_value = mock_response
        
        path = download_file('http://test.com/file.zip')
        self.assertTrue(os.path.exists(path))
        with open(path, 'rb') as f:
            self.assertEqual(f.read(), b'chunk1chunk2')
        os.remove(path)

    @patch('flibusta.book_importer.requests.get')
    @patch('flibusta.book_importer.download_file')
    @patch('flibusta.book_importer.process_archive')
    @patch('flibusta.book_importer.os.path.exists')
    @patch('flibusta.book_importer.os.remove')
    def test_process_daily_updates(self, mock_remove, mock_exists, mock_process, mock_download, mock_get):
        mock_response = MagicMock()
        mock_response.text = '<a href="f.fb2.1-2.zip">link</a>'
        mock_get.return_value = mock_response
        mock_download.return_value = 'temp.zip'
        mock_exists.return_value = True
        
        process_daily_updates([])
            
        mock_process.assert_called_once_with('temp.zip', filters=[])
        mock_download.assert_called_once()
        mock_remove.assert_called_once_with('temp.zip')

    @patch('os.path.exists')
    @patch('os.path.isfile')
    @patch('os.listdir')
    @patch('flibusta.book_importer.process_archive')
    def test_process_local_path_dir(self, mock_process, mock_listdir, mock_isfile, mock_exists):
        mock_exists.return_value = True
        mock_isfile.return_value = False
        mock_listdir.return_value = ['book1.zip', 'other.txt']
        
        process_local_path('some/dir')
        
        mock_process.assert_called_once_with(os.path.join('some/dir', 'book1.zip'), filters=[])

    @patch('os.path.exists')
    @patch('os.path.isfile')
    @patch('flibusta.book_importer.process_archive')
    def test_process_local_path_file(self, mock_process, mock_isfile, mock_exists):
        mock_exists.return_value = True
        mock_isfile.return_value = True
        
        process_local_path('some/file.zip')
        
        mock_process.assert_called_once_with('some/file.zip', filters=[])

    @patch('os.path.exists')
    @patch('os.listdir')
    @patch('flibusta.book_importer.process_archive')
    def test_process_local_path_invalid(self, mock_process, mock_listdir, mock_exists):
        mock_exists.return_value = False
        with self.assertLogs('flibusta.book_importer', level='ERROR') as cm:
            process_local_path('invalid/path')
        self.assertTrue(any("Path 'invalid/path' does not exist" in output for output in cm.output))
        mock_process.assert_not_called()
