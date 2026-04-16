from django.test import TestCase, override_settings
from django.urls import reverse
from library.models import Author, Language, Book

@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class BookDetailSidebarTests(TestCase):
    """
    Tests for the sidebar in BookDetailView.
    """

    @classmethod
    def setUpTestData(cls):
        cls.lang_en = Language.objects.create(code='en', name='English')
        cls.author1 = Author.objects.create(first_name='John', last_name='Doe')
        cls.author2 = Author.objects.create(first_name='Jane', last_name='Smith')
        
        cls.book_single_author = Book.objects.create(title='Single Author Book', language=cls.lang_en)
        cls.book_single_author.authors.add(cls.author1)
        
        cls.book_multiple_authors = Book.objects.create(title='Multiple Authors Book', language=cls.lang_en)
        cls.book_multiple_authors.authors.add(cls.author1, cls.author2)

    def test_book_details_sidebar_contains_title(self):
        """
        Verify that the book title is present in the sidebar.
        """
        response = self.client.get(reverse('library:book_details', args=[self.book_single_author.id]))
        self.assertEqual(response.status_code, 200)
        # Check if title is inside the sidebar div
        self.assertContains(response, '<h4 class="fw-bold mb-1">Single Author Book</h4>', html=True)

    def test_book_details_sidebar_contains_author_links(self):
        """
        Verify that author links are present and point to the correct author detail pages.
        """
        response = self.client.get(reverse('library:book_details', args=[self.book_single_author.id]))
        self.assertEqual(response.status_code, 200)
        
        author_url = reverse('library:author_details', args=[self.author1.id])
        expected_link = f'<a href="{author_url}" class="text-decoration-none small d-block">{self.author1.full_name}</a>'
        self.assertContains(response, expected_link, html=True)

    def test_book_details_sidebar_multiple_authors(self):
        """
        Verify that multiple authors are displayed if present.
        """
        response = self.client.get(reverse('library:book_details', args=[self.book_multiple_authors.id]))
        self.assertEqual(response.status_code, 200)
        
        author1_url = reverse('library:author_details', args=[self.author1.id])
        author2_url = reverse('library:author_details', args=[self.author2.id])
        
        self.assertContains(response, author1_url)
        self.assertContains(response, self.author1.full_name)
        self.assertContains(response, author2_url)
        self.assertContains(response, self.author2.full_name)
