import io
import os
import pyzipper
from django.test import TestCase, override_settings
from django.urls import reverse
from django.core.files.base import ContentFile
from django.conf import settings
from parameterized import parameterized

from library.models import Author, Language, Book
from library.tests.epub_test_utils import create_epub_nested_chapters
from library.tests.fb2_test_utils import create_fb2_nested_chapters


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class BookDownloadViewTests(TestCase):
    """
    Tests for the BookDownloadView in library.views.
    """

    @classmethod
    def setUpTestData(cls):
        cls.author = Author.objects.create(first_name='John', last_name='Doe')
        cls.lang_en = Language.objects.create(code='en', name='English')
        
        # Book with no file
        cls.no_file_book = Book.objects.create(title='No File', language=cls.lang_en)

    def tearDown(self):
        """Clean up book files created during tests."""
        for book in Book.objects.all():
            if book.file:
                if os.path.exists(book.file.path):
                    os.remove(book.file.path)

    @parameterized.expand([
        ("epub", "Test EPUB", "epub", create_epub_nested_chapters, 'application/epub+zip', 'Doe_John_-_Test_EPUB.epub', False),
        ("fb2_zipped", "Test FB2 Zipped", "fb2", create_fb2_nested_chapters, 'application/x-fictionbook+xml', 'Doe_John_-_Test_FB2_Zipped.fb2', True),
        ("cyrillic_epub", "З москалями нема спільної мови", "epub", create_epub_nested_chapters, 'application/epub+zip', 'Бандера_Степан_Андрійович_-_З_москалями_нема_спільної_мови.epub', False, "Бандера, Степан, Андрійович"),
        ("cyrillic_fb2_zipped", "З москалями нема спільної мови", "fb2", create_fb2_nested_chapters, 'application/x-fictionbook+xml', 'Бандера_Степан_Андрійович_-_З_москалями_нема_спільної_мови.fb2', True, "Бандера, Степан, Андрійович"),
    ])
    def test_book_download_filename(self, name, title, file_type, create_func, expected_content_type, expected_filename, is_zipped, author_name=None):
        """
        Verify downloading books with various titles and authors (including Cyrillic).
        """
        if author_name:
            # Assuming format: "Last, First, Middle"
            parts = [p.strip() for p in author_name.split(',')]
            author = Author.objects.create(last_name=parts[0], first_name=parts[1], middle_name=parts[2] if len(parts)>2 else "")
        else:
            author = self.author

        book = Book.objects.create(
            title=title,
            language=self.lang_en,
            file_type=file_type,
            size=1024
        )
        book.authors.add(author)

        with create_func() as f:
            content = f.read()

        if is_zipped:
            zip_buffer = io.BytesIO()
            with pyzipper.AESZipFile(zip_buffer, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zf:
                zf.setpassword(settings.BOOK_PWD)
                zf.writestr(f'inner.{file_type}', content)
            zip_buffer.seek(0)
            book.file.save(f'test.{file_type}.zip', ContentFile(zip_buffer.read()))
        else:
            book.file.save(f'test.{file_type}', ContentFile(content))

        import urllib.parse
        quoted_filename = urllib.parse.quote(expected_filename)
        # Django FileResponse uses RFC 6266 format for non-ascii
        if expected_filename.isascii():
            expected_header = f'attachment; filename="{expected_filename}"'
        else:
            expected_header = f"attachment; filename*=utf-8''{quoted_filename}"

        response = self.client.get(reverse('library:book_download', args=[book.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], expected_content_type)
        self.assertEqual(response['Content-Disposition'], expected_header)
        self.assertEqual(b"".join(response.streaming_content), content)

    def test_book_download_multiple_authors(self):
        """
        Verify filename format for multiple authors: FirstAuthor_et_al_-_Title.
        """
        book = Book.objects.create(title='Test EPUB', language=self.lang_en)
        book.authors.add(self.author)
        author2 = Author.objects.create(first_name='Jane', last_name='Smith')
        book.authors.add(author2)
        book.file.save('test.epub', ContentFile(b"content"))
        
        response = self.client.get(reverse('library:book_download', args=[book.id]))
        self.assertEqual(response.status_code, 200)
        
        # Expected: Doe_John_et_al_-_Test_EPUB.epub
        expected_filename = 'Doe_John_et_al_-_Test_EPUB.epub'
        self.assertEqual(response['Content-Disposition'], f'attachment; filename="{expected_filename}"')

    def test_book_download_404_no_file(self):
        """
        Verify 404 if the book has no file.
        """
        response = self.client.get(reverse('library:book_download', args=[self.no_file_book.id]))
        self.assertEqual(response.status_code, 404)

    def test_book_download_404_invalid_id(self):
        """
        Verify 404 for non-existent book ID.
        """
        response = self.client.get(reverse('library:book_download', args=[999]))
        self.assertEqual(response.status_code, 404)
