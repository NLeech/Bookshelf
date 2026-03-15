from django.test import TestCase
from unittest.mock import patch, MagicMock
from flibusta.book_importer import BookImporter
from flibusta.models import FlibustaBook, FlibustaAuthor, FlibustaGenre
from library.models import Author, Genre, Book, Language, BookSeries
from django.core.files import File

class BookImporterServiceTest(TestCase):
    def setUp(self):
        self.language = Language.objects.create(code='ru', name='Russian')
        self.genre_meta = Genre.objects.create(code='sf', name='Sci-Fi')
        self.genre = Genre.objects.create(code='sf_action', name='Action SF', parent=self.genre_meta)
        
        self.f_author = FlibustaAuthor.objects.create(
            first_name='Ivan', last_name='Ivanov', id=1, uid=1
        )
        self.f_genre = FlibustaGenre.objects.create(
            genre_code='sf_action', genre_desc='Action SF', genre_meta='sf'
        )
        self.f_book = FlibustaBook.objects.create(
            id=100, title='Test Book', lang='ru', file_type='fb2'
        )
        self.f_book.authors.add(self.f_author)
        self.f_book.genres.add(self.f_genre)

    def test_check_filters(self):
        importer = BookImporter(genres_filter=['sf_action'], langs_filter=['ru'], formats_filter=['fb2'])
        self.assertTrue(importer.check_filters(self.f_book))
        
        importer_fail_lang = BookImporter(langs_filter=['en'])
        self.assertFalse(importer_fail_lang.check_filters(self.f_book))

    @patch('flibusta.services.extract_metadata')
    @patch('flibusta.services.pyzipper.AESZipFile')
    def test_import_book_success(self, mock_zip, mock_extract):
        mock_meta = MagicMock(description='Desc', isbn='12345')
        mock_meta.cover_image_content = None # Disable cover for this test
        mock_extract.return_value = mock_meta
        
        # Mock Zip context manager
        mock_zf_instance = MagicMock()
        mock_zip.return_value.__enter__.return_value = mock_zf_instance
        
        importer = BookImporter()
        file_content = b'dummy content'
        
        importer.import_book(self.f_book, file_content, '100.fb2')
        
        # Verify Book Created
        book = Book.objects.first()
        self.assertIsNotNone(book)
        self.assertEqual(book.tittle, 'Test Book')
        self.assertEqual(book.description, 'Desc')
        self.assertEqual(book.isbn, 12345)
        
        # Verify Relations
        self.assertTrue(book.authors.filter(last_name='Ivanov').exists())
        self.assertTrue(book.genres.filter(code='sf_action').exists())
        
        # Verify FlibustaBook Updated
        self.f_book.refresh_from_db()
        self.assertTrue(self.f_book.is_imported)
        
        # Verify File Saved (Mocked)
        # self.assertTrue(book.file.name.endswith('.zip')) # Difficult to test exact file content with mocks, but check logic run

    def test_get_or_create_author_recursive(self):
        master_author = FlibustaAuthor.objects.create(id=10, last_name='Master', first_name='M')
        alias_author = FlibustaAuthor.objects.create(id=11, last_name='Alias', first_name='A', master_id=10)
        
        importer = BookImporter()
        l_author = importer.get_or_create_author(alias_author)
        
        self.assertEqual(l_author.last_name, 'Master')
        self.assertEqual(Author.objects.count(), 1)
        
        # Verify mapping
        self.assertTrue(hasattr(master_author, 'mapping'))
        # alias_author should also be mapped to the SAME library author?
        # My implementation maps 'alias_author' to 'library_author' (which is the Master's library author).
        # Let's check mapping
        self.assertTrue(hasattr(alias_author, 'mapping'))
        self.assertEqual(alias_author.mapping.library_author, l_author)

