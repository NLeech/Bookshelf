from datetime import timedelta
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from library.models import Book, Language

User = get_user_model()

@override_settings(STORAGES={
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
})
class HomePageViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', password='password')
        cls.lang = Language.objects.create(code='en', name='English')

    def test_latest_arrivals_filtering(self):
        """Verify only books from the last 7 days are shown."""
        now = timezone.now()
        # Book added 8 days ago
        b1 = Book.objects.create(title='Old Book', language=self.lang)
        b1.created_at = now - timedelta(days=8)
        b1.save()
        
        # Book added 6 days ago
        b2 = Book.objects.create(title='New Book', language=self.lang)
        b2.created_at = now - timedelta(days=6)
        b2.save()

        response = self.client.get(reverse('library:home'))
        latest_books = response.context['latest_books']
        
        self.assertEqual(len(latest_books), 1)
        self.assertEqual(latest_books[0].title, 'New Book')

    def test_latest_arrivals_sorting(self):
        """Verify ordering by created_at DESC, then title ASC."""
        now = timezone.now()
        # Create books with same created_at but different titles
        # Using specific times to ensure they are within the 7-day window
        base_time = now - timedelta(days=1)
        
        b1 = Book.objects.create(title='B Book', language=self.lang)
        b1.created_at = base_time
        b1.save()
        
        b2 = Book.objects.create(title='A Book', language=self.lang)
        b2.created_at = base_time
        b2.save()
        
        # Create a book added today
        b3 = Book.objects.create(title='C Book', language=self.lang)
        b3.created_at = now
        b3.save()

        response = self.client.get(reverse('library:home'))
        latest_books = list(response.context['latest_books'])
        
        # Expected order: C Book (now), A Book (yesterday), B Book (yesterday)
        self.assertEqual(latest_books[0].title, 'C Book')
        self.assertEqual(latest_books[1].title, 'A Book')
        self.assertEqual(latest_books[2].title, 'B Book')

    def test_homepage_status_and_template(self):
        """Verify 200 OK and correct template."""
        response = self.client.get(reverse('library:home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'library/index.html')

    def test_homepage_unauthenticated_view(self):
        """Verify section visibility for guests."""
        response = self.client.get(reverse('library:home'))
        content = response.content.decode()
        
        self.assertIn('Search', content)
        self.assertIn('Latest Arrivals', content)
        self.assertNotIn('Reading List (Placeholder)', content)
        self.assertNotIn('Favorite Authors (Placeholder)', content)

    def test_homepage_authenticated_view(self):
        """Verify section visibility for logged-in users."""
        self.client.login(username='testuser', password='password')
        response = self.client.get(reverse('library:home'))
        content = response.content.decode()
        
        self.assertIn('Search', content)
        self.assertIn('Latest Arrivals', content)
        self.assertIn('Reading List (Placeholder)', content)
        self.assertIn('Favorite Authors (Placeholder)', content)

    def test_latest_arrivals_htmx_pagination(self):
        """Verify HTMX partial response and pagination content."""
        now = timezone.now()
        # Create 55 books to trigger pagination (PAGINATE_BY=50)
        for i in range(55):
            Book.objects.create(title=f'Book {i:02d}', language=self.lang, created_at=now)

        # Page 2 request via HTMX
        response = self.client.get(
            reverse('library:home'),
            HTTP_HX_REQUEST='true',
            data={'page': 2}
        )
        
        # Should return partial, so no <html> tag
        self.assertNotContains(response, '<html')
        # Should contain books from page 2 (index 50-54)
        # Note: Order is -created_at, title. Since created_at is same, it's title ASC.
        # titles are Book 00 to Book 54.
        # Page 1: Book 00 to Book 49
        # Page 2: Book 50 to Book 54
        content = response.content.decode()
        self.assertIn('Book 50', content)
        self.assertIn('Book 54', content)
        self.assertNotIn('Book 00', content)

    def test_homepage_no_latest_arrivals(self):
        """Verify empty state message."""
        response = self.client.get(reverse('library:home'))
        self.assertContains(response, "No new books added in the last 7 days.")

    def test_homepage_pagination_presence(self):
        """Verify pagination is present at both top and bottom of the list when multiple pages exist."""
        now = timezone.now()
        # Create 55 books to trigger pagination
        for i in range(55):
            Book.objects.create(title=f'Book {i:02d}', language=self.lang, created_at=now)

        response = self.client.get(reverse('library:home'))
        content = response.content.decode()
        
        # Count occurrences of pagination nav
        # Pagination uses <nav aria-label="Latest arrivals pagination" ...>
        self.assertEqual(content.count('aria-label="Latest arrivals pagination"'), 2)

    def test_homepage_jump_to_page(self):
        """Verify Jump to Page form presence and correct HTMX attributes."""
        now = timezone.now()
        for i in range(55):
            Book.objects.create(title=f'Book {i:02d}', language=self.lang, created_at=now)

        response = self.client.get(reverse('library:home'))
        content = response.content.decode()
        
        self.assertIn('Jump to Page', content)
        self.assertIn('hx-target="#latest-arrivals-container"', content)
        self.assertIn('hx-swap="outerHTML"', content)
