from unittest.mock import patch
from django.urls import reverse
from django.core.files.base import ContentFile
from django.contrib.auth import get_user_model
from django.core.cache import caches
from django.test import override_settings

from bookshelf.tests.base_test import BaseTestCase
from library.models import Author, Language, Book
from library.tests.epub_test_utils import create_epub_nested_chapters

User = get_user_model()


@override_settings(CACHES={
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
    'book_chapters': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}
})
class BookDetailViewCacheTests(BaseTestCase):
    """
    Tests for the BookDetailView caching logic.
    """

    @classmethod
    def setUpTestData(cls):
        cls.author = Author.objects.create(first_name='John', last_name='Doe')
        cls.lang_en = Language.objects.create(code='en', name='English')
        
        # EPUB Book with nested chapters
        cls.epub_book = Book.objects.create(title='Test EPUB', language=cls.lang_en)
        cls.epub_book.authors.add(cls.author)
        with create_epub_nested_chapters() as f:
            cls.epub_book.file.save('test.epub', ContentFile(f.read()))

        # Another EPUB Book
        cls.epub_book_2 = Book.objects.create(title='Test EPUB 2', language=cls.lang_en)
        cls.epub_book_2.authors.add(cls.author)
        with create_epub_nested_chapters() as f:
            cls.epub_book_2.file.save('test2.epub', ContentFile(f.read()))

        # User for authentication
        cls.user = User.objects.create_user(username='testuser', email='test@example.com', password='password')

    def setUp(self):
        self.client.login(username='testuser', password='password')
        self.cache = caches['book_chapters']
        self.cache.clear()

    def tearDown(self):
        # Ensure files are closed
        for book in Book.objects.all():
            if book.file:
                book.file.close()
        self.cache.clear()

    def test_chapters_cache_population(self):
        """
        Verify that a request to BookDetailView populates the cache.
        """
        cache_key = f'book_{self.epub_book.id}_chapters'
        self.assertIsNone(self.cache.get(cache_key))

        response = self.client.get(reverse('library:book', args=[self.epub_book.id]))
        self.assertEqual(response.status_code, 200)

        chapters = self.cache.get(cache_key)
        self.assertIsNotNone(chapters)
        self.assertEqual(len(chapters), 3)
        self.assertEqual(chapters[0].title, 'Chapter 1')

    def test_chapters_cache_hit(self):
        """
        Verify that subsequent requests retrieve data from the cache.
        We mock _get_chapters to verify it's only called once.
        """
        from library.views import BookDetailView

        # We patch _get_chapters on the class level and use side_effect to keep the original logic
        with patch.object(BookDetailView, '_get_chapters', side_effect=BookDetailView._get_chapters, autospec=True) as mocked_get_chapters:
            # First request - Cache Miss
            response1 = self.client.get(reverse('library:book', args=[self.epub_book.id]))
            self.assertEqual(response1.status_code, 200)
            self.assertEqual(mocked_get_chapters.call_count, 1)

            # Second request - Cache Hit
            response2 = self.client.get(reverse('library:book', args=[self.epub_book.id]))
            self.assertEqual(response2.status_code, 200)
            # Call count should still be 1
            self.assertEqual(mocked_get_chapters.call_count, 1)

    def test_cache_key_isolation(self):
        """
        Verify that different books use different cache keys and don't overlap.
        """
        # Request Book A
        self.client.get(reverse('library:book', args=[self.epub_book.id]))
        # Request Book B
        self.client.get(reverse('library:book', args=[self.epub_book_2.id]))

        cache_key_A = f'book_{self.epub_book.id}_chapters'
        cache_key_B = f'book_{self.epub_book_2.id}_chapters'

        chapters_A = self.cache.get(cache_key_A)
        chapters_B = self.cache.get(cache_key_B)

        self.assertIsNotNone(chapters_A)
        self.assertIsNotNone(chapters_B)
        self.assertNotEqual(cache_key_A, cache_key_B)
        
        self.assertEqual(chapters_A[0].title, 'Chapter 1')
        self.assertEqual(chapters_B[0].title, 'Chapter 1')
