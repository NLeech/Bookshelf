from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.files.base import ContentFile
from django.utils.text import Truncator
from parameterized import parameterized

from library.models import Author, Language, Book
from library.tests.epub_test_utils import create_epub_nested_chapters

User = get_user_model()


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class AccessControlTests(TestCase):
    """
    Tests for book access control, including authentication, permissions,
    and content truncation.
    """

    @classmethod
    def setUpTestData(cls):
        # Setup basic models
        cls.author = Author.objects.create(first_name='John', last_name='Doe')
        cls.lang_en = Language.objects.create(code='en', name='English')
        
        # Create a book with a long content to test truncation
        # 600 words of "word "
        long_content = 'word ' * 600
        cls.book = Book.objects.create(title='Test Book', language=cls.lang_en)
        cls.book.authors.add(cls.author)
        
        # We use a custom epub creation here to ensure enough words
        with create_epub_nested_chapters(content=long_content) as f:
            cls.book.file.save('test.epub', ContentFile(f.read()))

        # Setup users
        cls.user_no_access = User.objects.create_user(
            username='no_access',
            email='no_access@example.com',
            password='password'
        )
        cls.user_with_access = User.objects.create_user(
            username='with_access',
            email='with_access@example.com',
            password='password'
        )
        
        # Assign permission to user_with_access via group
        group = Group.objects.get(name='Book access')
        cls.user_with_access.groups.add(group)

    def test_book_detail_unauthenticated(self):
        """
        Verify that unauthenticated users are redirected to login.
        """
        response = self.client.get(reverse('library:book', args=[self.book.id]))
        # Django's LoginRequiredMixin redirects to settings.LOGIN_URL
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('account_login'), response.url)

    def test_book_detail_authenticated_no_group(self):
        """
        Verify that authenticated users without 'view_book' see truncated content.
        """
        self.client.login(username='no_access', password='password')
        response = self.client.get(reverse('library:book', args=[self.book.id]))
        self.assertEqual(response.status_code, 200)
        
        current_chapter = response.context['current_chapter']
        
        # Check for truncation marker (Truncator may use ... or …)
        self.assertTrue('...' in current_chapter.content or '…' in current_chapter.content)

    def test_book_detail_authenticated_with_group(self):
        """
        Verify that authenticated users with 'view_book' see full content.
        """
        self.client.login(username='with_access', password='password')
        response = self.client.get(reverse('library:book', args=[self.book.id]))
        self.assertEqual(response.status_code, 200)
        
        current_chapter = response.context['current_chapter']
        
        # Should NOT have truncation marker
        self.assertNotIn('...', current_chapter.content)
        self.assertNotIn('…', current_chapter.content)

    def test_book_download_unauthenticated(self):
        """
        Verify that unauthenticated users cannot download books (redirect to login).
        """
        response = self.client.get(reverse('library:book_download', args=[self.book.id]))
        self.assertEqual(response.status_code, 302)
        # LoginRequiredMixin redirects to settings.LOGIN_URL which is /accounts/login/
        self.assertIn('/accounts/login/', response.url)

    def test_book_download_authenticated_no_group(self):
        """
        Verify that authenticated users without 'view_book' get 403 Forbidden on download.
        """
        self.client.login(username='no_access', password='password')
        response = self.client.get(reverse('library:book_download', args=[self.book.id]))
        self.assertEqual(response.status_code, 403)

    def test_book_download_authenticated_with_group(self):
        """
        Verify that authenticated users with 'view_book' can download books.
        """
        self.client.login(username='with_access', password='password')
        response = self.client.get(reverse('library:book_download', args=[self.book.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/epub+zip')

    def test_book_item_labels(self):
        """
        Verify "Preview" vs "Read" labels in book_item.html based on user permissions.
        """
        # Test with user_no_access
        self.client.login(username='no_access', password='password')
        response = self.client.get(reverse('library:home')) # book_item is used in latest arrivals
        self.assertContains(response, 'Preview')
        self.assertNotContains(response, '>Read<') # Use >Read< to avoid matching parts of other words
        
        # Test with user_with_access
        self.client.login(username='with_access', password='password')
        response = self.client.get(reverse('library:home'))
        self.assertContains(response, 'Read')
        self.assertNotContains(response, '>Preview<')

    def test_book_item_download_visibility(self):
        """
        Verify download link visibility in book_item.html based on user permissions.
        """
        download_url = reverse('library:book_download', args=[self.book.id])
        
        # Test with user_no_access
        self.client.login(username='no_access', password='password')
        response = self.client.get(reverse('library:home'))
        self.assertNotContains(response, download_url)
        
        # Test with user_with_access
        self.client.login(username='with_access', password='password')
        response = self.client.get(reverse('library:home'))
        self.assertContains(response, download_url)
