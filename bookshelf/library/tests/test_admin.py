from django.contrib.admin.sites import AdminSite
from bookshelf.tests.base_test import BaseTestCase
from library.models import Book, Genre, BookSeries, Author, Language
from library.admin import BookAdmin, GenreAdmin, BookSeriesAdmin


class MockRequest:
    pass


class BookAdminTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.site = AdminSite()
        self.book_admin = BookAdmin(Book, self.site)
        self.language = Language.objects.create(code='en', name='English')

    def test_book_admin_registered(self):
        from django.contrib import admin
        self.assertIsInstance(admin.site._registry[Book], BookAdmin)

    def test_book_admin_list_display(self):
        self.assertIn('title', self.book_admin.list_display)
        self.assertIn('language', self.book_admin.list_display)

    def test_book_admin_readonly_fields(self):
        self.assertIn('cover_thumbnail', self.book_admin.readonly_fields)

    def test_book_admin_autocomplete_fields(self):
        self.assertIn('authors', self.book_admin.autocomplete_fields)
        self.assertIn('genres', self.book_admin.autocomplete_fields)

    def test_related_admins_have_search_fields(self):
        genre_admin = GenreAdmin(Genre, self.site)
        series_admin = BookSeriesAdmin(BookSeries, self.site)
        
        self.assertTrue(genre_admin.search_fields)
        self.assertTrue(series_admin.search_fields)

    def test_book_series_admin_has_book_inline(self):
        from library.admin import BookSeriesBookInline
        series_admin = BookSeriesAdmin(BookSeries, self.site)
        self.assertIn(BookSeriesBookInline, series_admin.inlines)

    def test_book_series_book_inline_fields(self):
        from library.admin import BookSeriesBookInline
        inline = BookSeriesBookInline(BookSeries, self.site)
        self.assertIn('get_cover_preview', inline.fields)
        self.assertIn('book', inline.fields)
        self.assertIn('sequence_number', inline.fields)
        self.assertIn('get_cover_preview', inline.readonly_fields)
        self.assertIn('book', inline.readonly_fields)

    def test_book_series_book_inline_ordering(self):
        from library.admin import BookSeriesBookInline
        inline = BookSeriesBookInline(BookSeries, self.site)
        self.assertEqual(inline.ordering, ('sequence_number',))
