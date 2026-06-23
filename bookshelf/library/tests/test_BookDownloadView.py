import io
import zipfile
import pyzipper
from django.urls import reverse
from django.core.files.base import ContentFile
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from parameterized import parameterized

from bookshelf.tests.base_test import BaseTestCase
from library.models import Author, Language, Book
from library.tests.epub_test_utils import create_epub_nested_chapters
from library.tests.fb2_test_utils import create_fb2_nested_chapters

User = get_user_model()


class BookDownloadViewTests(BaseTestCase):
    """
    Tests for the BookDownloadView in library.views.
    """

    @classmethod
    def setUpTestData(cls):
        cls.author = Author.objects.create(first_name='John', last_name='Doe')
        cls.lang_en = Language.objects.create(code='en', name='English')
        
        # Book with no file
        cls.no_file_book = Book.objects.create(title='No File', language=cls.lang_en)

        # User for authentication
        cls.user = User.objects.create_user(username='testuser', email='test@example.com', password='password')
        group, _ = Group.objects.get_or_create(name='Book access')
        cls.user.groups.add(group)

    def setUp(self):
        self.client.login(username='testuser', password='password')

    @parameterized.expand([
        ("epub", "Test EPUB", "epub", create_epub_nested_chapters, 'application/epub+zip', 'Doe_John_-_Test_EPUB.epub', False, False),
        ("fb2_zipped", "Test FB2 Zipped", "fb2", create_fb2_nested_chapters, 'application/fb2+zip', 'Doe_John_-_Test_FB2_Zipped.fb2.zip', True, True),
        ("cyrillic_epub", "З москалями нема спільної мови", "epub", create_epub_nested_chapters, 'application/epub+zip', 'Бандера_Степан_Андрійович_-_З_москалями_нема_спільної_мови.epub', False, False, "Бандера, Степан, Андрійович"),
        ("cyrillic_fb2_zipped", "З москалями нема спільної мови", "fb2", create_fb2_nested_chapters, 'application/fb2+zip', 'Бандера_Степан_Андрійович_-_З_москалями_нема_спільної_мови.fb2.zip', True, True, "Бандера, Степан, Андрійович"),
    ])
    def test_book_download_filename(self, name, title, file_type, create_func, expected_content_type, expected_filename, is_zipped, delivered_zipped, author_name=None):
        """
        Verify downloading books with various titles and authors (including Cyrillic).

        FB2 books are delivered zip-wrapped (``application/fb2+zip``); the body is
        a plain ZIP whose single entry holds the original FB2 bytes.
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

        body = b"".join(response.streaming_content)
        if delivered_zipped:
            inner_name = expected_filename[:-len('.zip')]
            with zipfile.ZipFile(io.BytesIO(body)) as zf:
                self.assertEqual(zf.namelist(), [inner_name])
                self.assertEqual(zf.read(inner_name), content)
        else:
            self.assertEqual(body, content)

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
        # Make sure the book doesn't exist
        invalid_id = 999
        while Book.objects.filter(id=invalid_id).exists():
            invalid_id += 1
            
        response = self.client.get(reverse('library:book_download', args=[invalid_id]))
        self.assertEqual(response.status_code, 404)
