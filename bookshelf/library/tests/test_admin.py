from django.test import TestCase
from django.contrib.admin.sites import AdminSite
from library.models import Book, Genre, BookSeries, Author, Language
from library.admin import BookAdmin, GenreAdmin, BookSeriesAdmin


class MockRequest:
    pass


class BookAdminTest(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.book_admin = BookAdmin(Book, self.site)
        self.language = Language.objects.create(code='en', name='English')

    def test_book_admin_registered(self):
        from django.contrib import admin
        self.assertIsInstance(admin.site._registry[Book], BookAdmin)

    def test_book_admin_list_display(self):
        self.assertIn('title', self.book_admin.list_display)
        self.assertIn('language', self.book_admin.list_display)
        self.assertIn('cover_thumbnail', self.book_admin.list_display)

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
