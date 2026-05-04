from datetime import timedelta
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from library.models import Book, Language, Author, BookSeries

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
        self.assertNotIn('Reading List', content)
        self.assertNotIn('Favorite Authors', content)

    def test_homepage_authenticated_view(self):
        """Verify section visibility for logged-in users."""
        self.client.login(username='testuser', password='password')
        response = self.client.get(reverse('library:home'))
        content = response.content.decode()
        
        self.assertIn('Search', content)
        self.assertIn('Latest Arrivals', content)
        self.assertIn('Reading List', content)
        self.assertIn('Favorite Authors', content)

    def test_latest_arrivals_pagination_full_page(self):
        """Verify pagination content on full page load (non-HTMX)."""
        now = timezone.now()
        # Create 55 books to trigger pagination (PAGINATE_BY=50)
        for i in range(55):
            Book.objects.create(title=f'Book {i:02d}', language=self.lang, created_at=now)

        # Page 2 request
        response = self.client.get(
            reverse('library:home'),
            data={'page': 2}
        )
        
        # Should contain books from page 2 (index 50-54)
        content = response.content.decode()
        self.assertIn('Book 50', content)
        self.assertIn('Book 54', content)
        self.assertNotIn('Book 00', content)
        self.assertIn('<html', content)

    def test_latest_arrivals_pagination_htmx(self):
        """Verify HTMX partial response for latest arrivals pagination."""
        now = timezone.now()
        # Create 55 books to trigger pagination
        for i in range(55):
            Book.objects.create(title=f'Book {i:02d}', language=self.lang, created_at=now)

        # Page 2 HTMX request targeting latest-arrivals-container
        response = self.client.get(
            reverse('library:home'),
            data={'page': 2},
            HTTP_HX_REQUEST='true',
            HTTP_HX_TARGET='latest-arrivals-container'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('library/index.html#latest_arrivals', response.template_name)
        
        content = response.content.decode()
        self.assertIn('Book 50', content)
        self.assertIn('Book 54', content)
        self.assertNotIn('Book 00', content)
        # Should not contain the full layout
        self.assertNotContains(response, '<html')
        self.assertIn('id="latest-arrivals-container"', content)

    def test_homepage_htmx_search_vs_pagination(self):
        """Verify correct partial is returned based on HX-Target."""
        # Search target
        response = self.client.get(
            reverse('library:home'),
            {'q': 'test'},
            HTTP_HX_REQUEST='true',
            HTTP_HX_TARGET='search-results'
        )
        self.assertIn('library/index.html#search_results', response.template_name)

        # Pagination target
        response = self.client.get(
            reverse('library:home'),
            {'page': 1},
            HTTP_HX_REQUEST='true',
            HTTP_HX_TARGET='latest-arrivals-container'
        )
        self.assertIn('library/index.html#latest_arrivals', response.template_name)

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
        
        self.assertIn('Jump', content)
        self.assertIn('hx-target="#latest-arrivals-container"', content)
        self.assertIn('hx-swap="outerHTML"', content)

    def test_homepage_disclaimer_presence(self):
        """Verify the disclaimer footer is present on the homepage."""
        response = self.client.get(reverse('library:home'))
        self.assertContains(
            response, 
            'Disclaimer: This website does not host or distribute full copies of any books.'
        )


    def test_home_page_with_search_query(self):
        "Verify search results in context when q is provided, and latest arrivals still present."
        Book.objects.create(title='Searchable Book', language=self.lang)
        response = self.client.get(reverse('library:home'), {'q': 'Searchable'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('search_results', response.context)
        self.assertEqual(response.context['search_results']['books_count'], 1)
        self.assertEqual(response.context['query'], 'Searchable')
        # Latest arrivals should still be in context
        self.assertIn('latest_books', response.context)

    def test_home_page_search_htmx(self):
        "Verify partial rendering for HTMX search requests."
        response = self.client.get(
            reverse('library:home'),
            {'q': 'test'},
            HTTP_HX_REQUEST='true'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('library/index.html#search_results', response.template_name)
        # Should not contain the full layout
        self.assertNotContains(response, '<html')

    def test_home_page_search_htmx_authenticated(self):
        "Verify partial rendering for HTMX search requests when authenticated."
        self.client.login(username='testuser', password='password')
        response = self.client.get(
            reverse('library:home'),
            {'q': 'test'},
            HTTP_HX_REQUEST='true'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('library/index.html#search_results', response.template_name)

    def test_home_page_clear_search_htmx(self):
        "Verify that an empty q parameter via HTMX results in search results partial (which will clear it)."
        response = self.client.get(
            reverse('library:home'),
            {'q': ''},
            HTTP_HX_REQUEST='true'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('library/index.html#search_results', response.template_name)
        self.assertIn('search_results', response.context)
        self.assertEqual(response.context['search_results']['total_count'], 0)

    def test_home_page_no_query_htmx(self):
        "Verify that no q parameter via HTMX results in search results partial (which will clear it)."
        response = self.client.get(
            reverse('library:home'),
            HTTP_HX_REQUEST='true'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('library/index.html#search_results', response.template_name)
        self.assertNotIn('search_results', response.context)

    def test_triple_independent_pagination(self):
        """Verify all three search paginators work independently."""
        # Create 60 authors, 60 books, and 60 series matching "Test"
        for i in range(60):
            Author.objects.create(last_name=f'Test Author {i:02d}')
            Book.objects.create(title=f'Test Book {i:02d}', language=self.lang)
            BookSeries.objects.create(name=f'Test Series {i:02d}')

        # Request with different page numbers for each
        response = self.client.get(
            reverse('library:home'),
            data={'q': 'Test', 'apage': 2, 'bpage': 1, 'spage': 1}
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['authors_page_obj'].number, 2)
        self.assertEqual(response.context['books_page_obj'].number, 1)
        self.assertEqual(response.context['series_page_obj'].number, 1)
        
        self.assertIn('authors_page_obj', response.context)
        self.assertIn('books_page_obj', response.context)
        self.assertIn('series_page_obj', response.context)

    def test_htmx_partial_authors(self):
        """Verify HTMX partial for authors search pagination."""
        for i in range(60):
            Author.objects.create(last_name=f'Test Author {i:02d}')

        response = self.client.get(
            reverse('library:home'),
            data={'q': 'Test', 'apage': 2},
            HTTP_HX_REQUEST='true',
            HTTP_HX_TARGET='search-authors-body'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('library/index.html#search_authors_results', response.template_name)
        content = response.content.decode()
        self.assertIn('hx-target="#search-authors-body"', content)
        self.assertIn('Test Author 50', content)
        self.assertNotIn('Test Author 00', content)

    def test_htmx_partial_books(self):
        """Verify HTMX partial for books search pagination."""
        for i in range(60):
            Book.objects.create(title=f'Test Book {i:02d}', language=self.lang)

        response = self.client.get(
            reverse('library:home'),
            data={'q': 'Test', 'bpage': 2},
            HTTP_HX_REQUEST='true',
            HTTP_HX_TARGET='search-books-body'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('library/index.html#search_books_results', response.template_name)
        content = response.content.decode()
        self.assertIn('hx-target="#search-books-body"', content)
        self.assertIn('Test Book 50', content)
        self.assertNotIn('Test Book 00', content)

    def test_htmx_partial_series(self):
        """Verify HTMX partial for series search pagination."""
        for i in range(60):
            BookSeries.objects.create(name=f'Test Series {i:02d}')

        response = self.client.get(
            reverse('library:home'),
            data={'q': 'Test', 'spage': 2},
            HTTP_HX_REQUEST='true',
            HTTP_HX_TARGET='search-series-body'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('library/index.html#search_series_results', response.template_name)
        content = response.content.decode()
        self.assertIn('hx-target="#search-series-body"', content)
        self.assertIn('Test Series 50', content)
        self.assertNotIn('Test Series 00', content)
