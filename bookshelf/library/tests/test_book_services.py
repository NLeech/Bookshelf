import io
import os
import pyzipper
from unittest import mock
from django.test import TestCase
from django.conf import settings
from django.core.files.base import ContentFile
from parameterized import parameterized

from library.models import Book, Language, Author, Genre, BookSeries
from library.services import (
    get_book_extractor,
    flatten_chapters,
    sanitize_filename,
    get_book_file_content,
    get_languages,
    get_genres_tree,
    search_entities
)
from library.book_utils import EpubBookFile, Fb2BookFile
from library.tests.epub_test_utils import create_epub_one_author
from library.tests.fb2_test_utils import create_fb2_one_author

class ChapterMock:
    def __init__(self, title, subchapters=None):
        self.title = title
        self.subchapters = subchapters or []
        self.flat_index = None

class BookServicesTest(TestCase):
    def setUp(self):
        self.language = Language.objects.create(code='en', name='English')

    def test_get_book_extractor_no_file(self):
        """Test with book.file = None."""
        book = Book.objects.create(title="No File", language=self.language)
        extractor = get_book_extractor(book)
        self.assertIsNone(extractor)

    @parameterized.expand([
        ("epub", ".epub", create_epub_one_author, EpubBookFile),
        ("fb2", ".fb2", create_fb2_one_author, Fb2BookFile),
    ])
    def test_get_book_extractor_direct(self, name, extension, create_func, expected_cls):
        """Test direct extraction for EPUB and FB2."""
        with create_func() as stream:
            content = stream.read()
        
        book = Book.objects.create(title=f"Test {name}", language=self.language)
        book.file.save(f"test{extension}", ContentFile(content))
        
        extractor = get_book_extractor(book)
        self.assertIsInstance(extractor, expected_cls)
        # Cleanup file
        if book.file:
            os.remove(book.file.path)

    @parameterized.expand([
        ("zip_epub", ".epub", create_epub_one_author, EpubBookFile),
        ("zip_fb2", ".fb2", create_fb2_one_author, Fb2BookFile),
    ])
    def test_get_book_extractor_zip(self, name, inner_ext, create_func, expected_cls):
        """Test extraction from password-protected ZIP."""
        with create_func() as stream:
            inner_content = stream.read()
        
        zip_buffer = io.BytesIO()
        with pyzipper.AESZipFile(zip_buffer, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zf:
            zf.setpassword(settings.BOOK_PWD)
            zf.writestr(f"inner{inner_ext}", inner_content)
        
        book = Book.objects.create(title=f"Test {name}", language=self.language)
        book.file.save(f"test_{name}.zip", ContentFile(zip_buffer.getvalue()))
        
        extractor = get_book_extractor(book)
        self.assertIsInstance(extractor, expected_cls)
        # Cleanup file
        if book.file:
            os.remove(book.file.path)

    def test_get_book_extractor_unsupported(self):
        """Test with unsupported extension."""
        book = Book.objects.create(title="Unsupported", language=self.language)
        book.file.save("test.txt", ContentFile(b"some text content"))
        
        extractor = get_book_extractor(book)
        self.assertIsNone(extractor)
        # Cleanup file
        if book.file:
            os.remove(book.file.path)

    def test_get_book_extractor_invalid_zip(self):
        """Test with invalid or damaged ZIP file."""
        book = Book.objects.create(title="Invalid ZIP", language=self.language)
        # Case 1: Text file renamed to .zip
        book.file.save("invalid.zip", ContentFile(b"not a zip content"))
        
        with self.assertLogs('library.services', level='ERROR') as cm:
            extractor = get_book_extractor(book)
            self.assertIsNone(extractor)
            self.assertTrue(any("Failed to extract book from ZIP" in output for output in cm.output))
        
        # Cleanup file
        if book.file:
            os.remove(book.file.path)

    def test_get_book_extractor_empty_zip(self):
        """Test with empty ZIP file."""
        zip_buffer = io.BytesIO()
        with pyzipper.AESZipFile(zip_buffer, 'w') as zf:
            zf.setpassword(settings.BOOK_PWD)
            # No files added
        
        book = Book.objects.create(title="Empty ZIP", language=self.language)
        book.file.save("empty.zip", ContentFile(zip_buffer.getvalue()))
        
        extractor = get_book_extractor(book)
        self.assertIsNone(extractor)
        # Cleanup file
        if book.file:
            os.remove(book.file.path)

    def test_get_book_extractor_zip_unsupported(self):
        """Test extraction from ZIP containing unsupported file extension."""
        zip_buffer = io.BytesIO()
        with pyzipper.AESZipFile(zip_buffer, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zf:
            zf.setpassword(settings.BOOK_PWD)
            zf.writestr("test.txt", b"plain text content")
        
        book = Book.objects.create(title="ZIP Unsupported", language=self.language)
        book.file.save("unsupported.zip", ContentFile(zip_buffer.getvalue()))
        
        extractor = get_book_extractor(book)
        self.assertIsNone(extractor)
        # Cleanup file
        if book.file:
            os.remove(book.file.path)

    def test_flatten_chapters_nested(self):
        """Test flattening of nested chapters."""
        c1_1 = ChapterMock("C1.1")
        c1_2 = ChapterMock("C1.2")
        c1 = ChapterMock("C1", subchapters=[c1_1, c1_2])
        c2 = ChapterMock("C2")
        
        chapters = [c1, c2]
        flat_list, next_index = flatten_chapters(chapters, index_start=10)
        
        self.assertEqual(len(flat_list), 4)
        self.assertEqual(flat_list[0].title, "C1")
        self.assertEqual(flat_list[0].flat_index, 10)
        
        self.assertEqual(flat_list[1].title, "C1.1")
        self.assertEqual(flat_list[1].flat_index, 11)
        
        self.assertEqual(flat_list[2].title, "C1.2")
        self.assertEqual(flat_list[2].flat_index, 12)
        
        self.assertEqual(flat_list[3].title, "C2")
        self.assertEqual(flat_list[3].flat_index, 13)
        
        self.assertEqual(next_index, 14)

    @parameterized.expand([
        ("Normal", "Doe, John - Test Book", "Doe_John_-_Test_Book"),
        ("Accents", "Möller, Jörn - Über", "Möller_Jörn_-_Über"),
        ("Special", "Author: Title?", "Author_-_Title"),
        ("Spaces", "  Author   Title  ", "Author_Title"),
        ("Double Underscore", "Author__Title", "Author_Title"),
        ("Leading Dot", ".Author", "Author"),
        ("Cyrillic", "Тарас Шевченко - Заповіт", "Тарас_Шевченко_-_Заповіт"),
    ])
    def test_sanitize_filename(self, name, input_str, expected):
        """Test sanitize_filename utility (on base names)."""
        self.assertEqual(sanitize_filename(input_str), expected)

    @parameterized.expand([
        ("epub_direct", "EPUB Direct", "epub", "application/epub+zip", False, True),
        ("fb2_direct", "FB2 Direct", "fb2", "application/x-fictionbook+xml", False, True),
        ("epub_zipped", "EPUB Zipped", "epub", "application/epub+zip", True, True),
        ("fb2_zipped", "FB2 Zipped", "fb2", "application/x-fictionbook+xml", True, True),
        ("no_authors", "No Author", "epub", "application/epub+zip", False, False),
    ])
    def test_get_book_file_content_parameterized(self, name, title, ext, expected_type, is_zipped, has_author):
        """Test get_book_file_content with various scenarios using parameterization."""
        book = Book.objects.create(title=title, language=self.language)
        if has_author:
            author = Author.objects.create(first_name='John', last_name='Doe')
            book.authors.add(author)
            expected_author_part = "Doe_John"
        else:
            expected_author_part = "Unknown"

        content = b"fake content"
        if is_zipped:
            zip_buffer = io.BytesIO()
            with pyzipper.AESZipFile(zip_buffer, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zf:
                zf.setpassword(settings.BOOK_PWD)
                zf.writestr(f"inner.{ext}", content)
            book.file.save(f"test.{ext}.zip", ContentFile(zip_buffer.getvalue()))
        else:
            book.file.save(f"test.{ext}", ContentFile(content))

        filename, result_content, content_type = get_book_file_content(book)
        
        expected_filename = f"{expected_author_part}_-_{title.replace(' ', '_')}.{ext}"
        self.assertEqual(filename, expected_filename)
        self.assertEqual(result_content, content)
        self.assertEqual(content_type, expected_type)
        
        if book.file:
            os.remove(book.file.path)

    def test_get_book_file_content_mimetype_registration(self):
        """Specifically cover mimetypes.add_type lines by mocking types_map to be empty."""
        author = Author.objects.create(first_name='John', last_name='Doe')
        book = Book.objects.create(title="Mime Test", language=self.language)
        book.authors.add(author)
        book.file.save("test.epub", ContentFile(b"content"))

        import mimetypes
        # Mock mimetypes.types_map to be an empty dict so .get() returns None
        with mock.patch('mimetypes.types_map', {}):
            with mock.patch('mimetypes.add_type') as mock_add:
                get_book_file_content(book)
                # Verify that add_type was called for both .epub and .fb2
                mock_add.assert_any_call('application/epub+zip', '.epub')
                mock_add.assert_any_call('application/x-fictionbook+xml', '.fb2')

        if book.file:
            os.remove(book.file.path)

    def test_get_book_file_content_missing_file(self):
        """Test get_book_file_content with book.file = None."""
        book = Book.objects.create(title="Missing File", language=self.language)
        filename, content, content_type = get_book_file_content(book)
        self.assertIsNone(filename)
        self.assertIsNone(content)
        self.assertIsNone(content_type)

    def test_get_book_file_content_zip_empty_list(self):
        """Test get_book_file_content with a ZIP that has no files in it."""
        zip_buffer = io.BytesIO()
        with pyzipper.AESZipFile(zip_buffer, 'w') as zf:
            zf.setpassword(settings.BOOK_PWD)
        
        book = Book.objects.create(title="Empty ZIP Book", language=self.language)
        book.file.save("empty.zip", ContentFile(zip_buffer.getvalue()))
        
        filename, content, content_type = get_book_file_content(book)
        self.assertIsNone(filename)
        self.assertIsNone(content)
        
        if book.file:
            os.remove(book.file.path)

    def test_get_book_file_content_zip_exception(self):
        """Test get_book_file_content ZIP extraction exception."""
        book = Book.objects.create(title="ZIP Exception", language=self.language)
        book.file.save("bad.zip", ContentFile(b"not a zip"))
        
        with self.assertLogs('library.services', level='ERROR') as cm:
            filename, content, content_type = get_book_file_content(book)
            self.assertIsNone(filename)
            self.assertTrue(any("Failed to extract book from ZIP" in output for output in cm.output))

        if book.file:
            os.remove(book.file.path)

    def test_get_book_file_content_read_exception(self):
        """Test get_book_file_content file read exception."""
        book = Book.objects.create(title="Read Exception", language=self.language)
        book.file.save("test.epub", ContentFile(b"content"))
        
        # Mock Path.read_bytes to raise an exception
        with mock.patch('library.services.Path.read_bytes', side_effect=Exception("Read error")):
            with self.assertLogs('library.services', level='ERROR') as cm:
                filename, content, content_type = get_book_file_content(book)
                self.assertIsNone(filename)
                self.assertTrue(any("Failed to read book file" in output for output in cm.output))

        if book.file:
            os.remove(book.file.path)

    def test_get_languages_with_filtered_queryset(self):
        """Verify get_languages() returns correct book counts when filtered."""
        lang_en = self.language
        lang_fr = Language.objects.create(name='French', code='fr')
        genre1 = Genre.objects.create(name='Sci-Fi', code='sf')
        
        b1 = Book.objects.create(title='Book 1', language=lang_en)
        b1.genres.add(genre1)
        b2 = Book.objects.create(title='Book 2', language=lang_fr)
        
        # Filtered by genre1: only lang_en should have a count
        qs = Book.objects.filter(genres=genre1)
        langs = get_languages(qs)
        
        en_res = next(l for l in langs if l.code == 'en')
        self.assertEqual(en_res.book_count, 1)
        self.assertFalse(any(l.code == 'fr' for l in langs))

    def test_get_genres_tree_with_filtered_queryset(self):
        """Verify get_genres_tree() returns correct hierarchy and counts when filtered."""
        lang_en = self.language
        lang_fr = Language.objects.create(name='French', code='fr')
        
        parent = Genre.objects.create(name='Fiction', code='fic')
        child = Genre.objects.create(name='Drama', code='dra', parent=parent)
        
        b1 = Book.objects.create(title='Drama En', language=lang_en)
        b1.genres.add(child)
        
        b2 = Book.objects.create(title='Drama Fr', language=lang_fr)
        b2.genres.add(child)
        
        # Filtered by English: both child and parent should be in tree.
        # Parent count is 0 (it doesn't sum up children), child count is 1.
        qs = Book.objects.filter(language=lang_en)
        tree = get_genres_tree(qs)
        
        self.assertEqual(len(tree), 1)
        self.assertEqual(tree[0]['genre'].code, 'fic')
        self.assertEqual(tree[0]['book_count'], 0)
        
        self.assertEqual(len(tree[0]['children']), 1)
        self.assertEqual(tree[0]['children'][0]['genre'].code, 'dra')
        self.assertEqual(tree[0]['children'][0]['book_count'], 1)


    def test_search_entities_authors(self):
        "Test searching authors by various fields and sorting."
        Author.objects.create(first_name='Isaac', last_name='Asimov', nickname='The Good Doctor')
        Author.objects.create(first_name='Arthur', middle_name='C.', last_name='Clarke')
        Author.objects.create(first_name='Robert', last_name='Heinlein')

        # Search by last name
        results = search_entities('Asimov')
        self.assertEqual(results['authors_count'], 1)
        self.assertEqual(results['authors'][0].last_name, 'Asimov')

        # Search by first name
        results = search_entities('Arthur')
        self.assertEqual(results['authors_count'], 1)
        self.assertEqual(results['authors'][0].first_name, 'Arthur')

        # Search by nickname
        results = search_entities('Doctor')
        self.assertEqual(results['authors_count'], 1)
        self.assertEqual(results['authors'][0].last_name, 'Asimov')

        # Search multiple
        results = search_entities('a')
        # Isaac Asimov and Arthur Clarke have 'a' or 'A' in their names. Robert Heinlein does not.
        self.assertEqual(results['authors_count'], 2)
        # Sorting: Asimov, Clarke
        self.assertEqual(results['authors'][0].last_name, 'Asimov')
        self.assertEqual(results['authors'][1].last_name, 'Clarke')

    def test_search_entities_books(self):
        "Test searching books by title."
        b1 = Book.objects.create(title='The Foundation', language=self.language)
        b2 = Book.objects.create(title='Foundation and Empire', language=self.language)
        b3 = Book.objects.create(title='Stranger in a Strange Land', language=self.language)

        results = search_entities('Foundation')
        self.assertEqual(results['books_count'], 2)
        self.assertEqual(results['books'][0].title, 'Foundation and Empire')
        self.assertEqual(results['books'][1].title, 'The Foundation')

    def test_search_entities_series(self):
        "Test searching series by name."
        BookSeries.objects.create(name='Foundation')
        BookSeries.objects.create(name='Robot')
        BookSeries.objects.create(name='Empire')

        results = search_entities('o')
        self.assertEqual(results['series_count'], 2)
        # Sorting: Foundation, Robot
        self.assertEqual(results['series'][0].name, 'Foundation')
        self.assertEqual(results['series'][1].name, 'Robot')

    def test_search_entities_empty_query(self):
        "Test search with empty query."
        results = search_entities('')
        self.assertEqual(results['total_count'], 0)
        self.assertFalse(results['authors'].exists())
        self.assertFalse(results['books'].exists())
        self.assertFalse(results['series'].exists())

    def test_search_entities_no_results(self):
        "Test search with no matches."
        results = search_entities('NonExistentQueryString')
        self.assertEqual(results['total_count'], 0)
