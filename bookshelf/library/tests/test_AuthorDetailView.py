from datetime import timedelta
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from parameterized import parameterized

from library.models import Author, Language, Genre, Book, BookSeries, BookSeriesLink


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class AuthorDetailViewTests(TestCase):
    """
    Tests for the AuthorDetailView in library.views.
    """

    @classmethod
    def setUpTestData(cls):
        # Create an author
        cls.author = Author.objects.create(first_name='Leo', last_name='Tolstoy')
        
        # Create languages
        cls.lang_ru = Language.objects.create(code='ru', name='Russian')
        cls.lang_en = Language.objects.create(code='en', name='English')
        
        # Create genres hierarchy
        cls.genre_parent = Genre.objects.create(name='Fiction', code='fiction')
        cls.genre_child = Genre.objects.create(name='Classic', code='classic', parent=cls.genre_parent)
        
        # Create books with different creation dates and languages
        now = timezone.now()
        
        # Book 1: Alpha 'A', Recent 3rd, lang ru, genre classic
        cls.book_1 = Book.objects.create(
            title='Anna Karenina', 
            language=cls.lang_ru,
            created_at=now - timedelta(days=2)
        )
        cls.book_1.authors.add(cls.author)
        cls.book_1.genres.add(cls.genre_child)
        
        # Book 2: Alpha 'W', Recent 1st, lang ru, genre fiction
        cls.book_2 = Book.objects.create(
            title='War and Peace', 
            language=cls.lang_ru,
            created_at=now
        )
        cls.book_2.authors.add(cls.author)
        cls.book_2.genres.add(cls.genre_parent)
        
        # Book 3: Alpha 'R', Recent 2nd, lang en, genre classic
        cls.book_3 = Book.objects.create(
            title='Resurrection', 
            language=cls.lang_en,
            created_at=now - timedelta(days=1)
        )
        cls.book_3.authors.add(cls.author)
        cls.book_3.genres.add(cls.genre_child)
        
        # Create a series and link books
        cls.series = BookSeries.objects.create(name='Great Novels')
        BookSeriesLink.objects.create(book=cls.book_1, series=cls.series, sequence_number=2)
        BookSeriesLink.objects.create(book=cls.book_2, series=cls.series, sequence_number=1)
        # book_3 is standalone

    def test_author_detail_view_status_code(self):
        """
        Verify the view returns 200 OK and uses the correct template.
        """
        response = self.client.get(reverse('library:author', args=[self.author.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'library/author.html')
        self.assertEqual(response.context['author'], self.author)

    def test_author_detail_view_404(self):
        """
        Verify the view returns 404 for a non-existent author.
        """
        response = self.client.get(reverse('library:author', args=[999]))
        self.assertEqual(response.status_code, 404)

    @parameterized.expand([
        ('alpha', 'alpha', ['Anna Karenina', 'Resurrection', 'War and Peace']),
        ('recent', 'recent', ['War and Peace', 'Resurrection', 'Anna Karenina']),
        ('series', 'series', []),
    ])
    def test_author_detail_view_tabs_parameterized(self, name, tab, expected_titles):
        """
        Verify tab logic (sorting for alpha and recent, existence for series).
        """
        response = self.client.get(reverse('library:author', args=[self.author.id]), {'tab': tab})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['active_tab'], tab)
        
        if tab == 'alpha':
            titles = [b.title for b in response.context['books_alpha']]
            self.assertEqual(titles, expected_titles)
        elif tab == 'recent':
            titles = [b.title for b in response.context['books_recent']]
            self.assertEqual(titles, expected_titles)
        elif tab == 'series':
            # Check series grouping
            self.assertEqual(len(response.context['series_list']), 1)
            series_info = response.context['series_list'][0]
            self.assertEqual(series_info['series'], self.series)
            self.assertEqual(series_info['count'], 2)
            # Check sequence (War and Peace is seq 1, Anna Karenina is seq 2)
            series_titles = [info['book'].title for info in series_info['books_info']]
            self.assertEqual(series_titles, ['War and Peace', 'Anna Karenina'])
            # Check standalone
            self.assertEqual(len(response.context['standalone_books']), 1)
            self.assertEqual(response.context['standalone_books'][0].title, 'Resurrection')

    @parameterized.expand([
        ('filter_lang_ru', {'lang': ['ru']}, 2), # Anna Karenina, War and Peace
        ('filter_lang_en', {'lang': ['en']}, 1), # Resurrection
        ('filter_genre_classic', {'genre': ['classic']}, 2), # Anna Karenina, Resurrection
        ('filter_genre_fiction', {'genre': ['fiction']}, 1), # War and Peace (Genre parent)
        ('filter_combined', {'lang': ['ru'], 'genre': ['classic']}, 1), # Anna Karenina
    ])
    def test_author_detail_view_filtering_parameterized(self, name, params, expected_count):
        """
        Verify filtering logic for languages and genres.
        """
        # Test on 'alpha' tab by default
        response = self.client.get(reverse('library:author', args=[self.author.id]), params)
        self.assertEqual(len(response.context['books_alpha']), expected_count)
        
        # Verify selected filters in context
        if 'lang' in params:
            self.assertEqual(response.context['selected_langs'], params['lang'])
        if 'genre' in params:
            self.assertEqual(response.context['selected_genres'], params['genre'])

    @parameterized.expand([
        ('alpha', 'alpha'),
        ('recent', 'recent'),
        ('series', 'series'),
    ])
    def test_author_detail_view_htmx_partials_parameterized(self, name, tab):
        """
        Verify that HTMX requests return the appropriate tab partial.
        """
        response = self.client.get(
            reverse('library:author', args=[self.author.id]),
            {'tab': tab},
            HTTP_HX_REQUEST='true'
        )
        self.assertEqual(response.status_code, 200)
        
        # In Django 6, the template_name will be updated with the block name
        expected_template = f'library/author.html#{tab}_tab'
        self.assertIn(expected_template, response.template_name)

    def test_author_detail_view_context_data(self):
        """
        Verify that available_languages and available_genres_tree are correctly populated.
        """
        response = self.client.get(reverse('library:author', args=[self.author.id]))
        self.assertIn('available_languages', response.context)
        self.assertIn('available_genres_tree', response.context)
        
        # ru and en both have books by this author
        langs = [l.code for l in response.context['available_languages']]
        self.assertIn('ru', langs)
        self.assertIn('en', langs)
        
        # Check genre tree - fiction should be there as it's used or a parent of classic
        genres = response.context['available_genres_tree']
        genre_names = [g['genre'].name for g in genres]
        self.assertIn('Fiction', genre_names)
