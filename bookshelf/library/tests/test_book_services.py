import io
import os
import pyzipper
from unittest import mock
from django.test import TestCase
from django.conf import settings
from django.core.files.base import ContentFile
from parameterized import parameterized

from library.models import Book, Language
from library.sevices import get_book_extractor, flatten_chapters
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
        
        with self.assertLogs('library.sevices', level='ERROR') as cm:
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
