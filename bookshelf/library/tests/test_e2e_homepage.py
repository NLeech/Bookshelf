from django.urls import reverse
from django.contrib.auth import get_user_model
from django.test import override_settings
from parameterized import parameterized
from allauth.account.models import EmailAddress

from library.models import Author, Book, BookSeries, Language
from library.tests.e2e_base import PlaywrightBaseTestCase

User = get_user_model()

@override_settings(PAGINATE_BY=10)
class HomepageE2ETest(PlaywrightBaseTestCase):
    user_password = 'testpassword123'
    email = 'testuser@example.com'

    def setUp(self):
        super().setUp()
        self.language = Language.objects.create(code='en', name='English')
        self.user = User.objects.create_user(username='testuser', email=self.email, password=self.user_password)
        EmailAddress.objects.create(user=self.user, email=self.email, primary=True, verified=True)

        self.author_unique = Author.objects.create(first_name='Unique', last_name='Author', nickname='Unique Author')
        self.series_unique = BookSeries.objects.create(name='Unique Series')
        self.book_unique = Book.objects.create(title='Unique Book Title', language=self.language)
        self.book_unique.authors.add(self.author_unique)
        self.book_unique.series.add(self.series_unique)

        for i in range(1, 25):
            Book.objects.create(title=f'Pagination Book {i:02d}', language=self.language)

    def test_homepage_anonymous_visibility(self):
        self.page.goto(self.live_server_url)
        self.assertEqual(self.page.title(), 'Bookshelf')
        self.page.wait_for_selector('input[name="q"]')
        self.assertTrue(self.page.locator('input[name="q"]').is_visible())
        self.assertTrue(self.page.locator('#latestArrivalsAccordion').is_visible())
        self.assertFalse(self.page.locator('#readingListAccordion').is_visible())
        self.assertFalse(self.page.locator('#favoriteAuthorsAccordion').is_visible())

    def test_homepage_authenticated_visibility(self):
        self.page.goto(self.live_server_url + reverse('account_login'))
        self.page.fill('input[name="login"]', self.email)
        self.page.fill('input[name="password"]', self.user_password)
        self.page.click('button[type="submit"]')
        self.page.wait_for_url(self.live_server_url + '/')
        self.page.wait_for_selector('#readingListAccordion')
        self.assertTrue(self.page.locator('#readingListAccordion').is_visible())
        self.assertTrue(self.page.locator('#favoriteAuthorsAccordion').is_visible())

    @parameterized.expand([
        ("Unique", True, True, True),
        ("Unique Book Title", True, False, False),
        ("Unique Author", False, True, False),
        ("NonExistent", False, False, False),
    ])
    def test_htmx_search(self, query, expect_book, expect_author, expect_series):
        self.page.goto(self.live_server_url)
        self.page.fill('input[name="q"]', query)
        self.page.press('input[name="q"]', 'Enter')
        self.wait_for_htmx()
        self.page.wait_for_selector('#search-results:has-text("Search results for")')
        results_text = self.page.locator('#search-results').text_content()
        if expect_book:
            self.assertIn('Unique Book Title', results_text)
        if expect_author:
            self.assertIn('Author, Unique', results_text)
        if expect_series:
            self.assertIn('Unique Series', results_text)
        if query == "NonExistent":
            self.assertIn('No authors found.', results_text)
            self.assertIn('No books found.', results_text)
            self.assertIn('No series found.', results_text)

    def test_htmx_pagination_navigation(self):
        self.page.goto(self.live_server_url)
        self.assertTrue(self.page.locator('li.page-item.disabled span.page-link:has-text("❮")').first.is_visible())
        self.assertTrue(self.page.locator('li.page-item.active:has-text("1")').first.is_visible())
        self.page.locator('a.page-link:has-text("2")').first.click()
        self.wait_for_htmx()
        self.assertTrue(self.page.locator('a.page-link:has-text("❮")').first.is_visible())
        self.assertTrue(self.page.locator('a.page-link:has-text("❯")').first.is_visible())
        self.assertTrue(self.page.locator('li.page-item.active:has-text("2")').first.is_visible())
        self.page.locator('a.page-link:has-text("❯")').first.click()
        self.wait_for_htmx()
        self.assertTrue(self.page.locator('li.page-item.disabled span.page-link:has-text("❯")').first.is_visible())
        self.assertTrue(self.page.locator('li.page-item.active:has-text("3")').first.is_visible())

    def test_htmx_pagination_jump(self):
        self.page.goto(self.live_server_url)
        self.page.locator('#jump-to-page-btn').first.click()
        self.page.wait_for_selector('input[name="page"]')
        self.page.fill('input[name="page"]', '3')
        self.page.press('input[name="page"]', 'Enter')
        self.wait_for_htmx()
        self.assertTrue(self.page.locator('li.page-item.active:has-text("3")').first.is_visible())
        self.assertTrue(self.page.locator('li.page-item.disabled span.page-link:has-text("❯")').first.is_visible())
