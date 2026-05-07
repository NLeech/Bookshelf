from django.urls import reverse
from parameterized import parameterized

from bookshelf.tests.base_test import BaseTestCase
from library.models import Author, Book, Language, Genre
from library.services import AlphabetTree


class BookListViewTests(BaseTestCase):
    """
    Tests for the BookListView in library.views.
    """

    @classmethod
    def setUpTestData(cls):
        # Create Languages
        cls.lang_en = Language.objects.create(code='en', name='English')
        cls.lang_ru = Language.objects.create(code='ru', name='Russian')

        # Create Authors
        cls.author1 = Author.objects.create(first_name='John', last_name='Doe')
        cls.author2 = Author.objects.create(first_name='Jane', last_name='Smith')

        # Create Genres
        cls.genre_fiction = Genre.objects.create(code='fiction', name='Fiction')
        cls.genre_scifi = Genre.objects.create(code='scifi', name='Sci-Fi', parent=cls.genre_fiction)
        cls.genre_fantasy = Genre.objects.create(code='fantasy', name='Fantasy', parent=cls.genre_fiction)
        cls.genre_history = Genre.objects.create(code='history', name='History')

        # Create Books
        # Book 1: English, Fiction, Author 1
        cls.book1 = Book.objects.create(title='A-Book', language=cls.lang_en)
        cls.book1.authors.add(cls.author1)
        cls.book1.genres.add(cls.genre_fiction)

        # Book 2: Russian, Sci-Fi, Author 1 & 2
        cls.book2 = Book.objects.create(title='B-Book', language=cls.lang_ru)
        cls.book2.authors.add(cls.author1, cls.author2)
        cls.book2.genres.add(cls.genre_scifi)

        # Book 3: English, History, Author 2
        cls.book3 = Book.objects.create(title='C-Book', language=cls.lang_en)
        cls.book3.authors.add(cls.author2)
        cls.book3.genres.add(cls.genre_history)

        # Create 50 more books for pagination tests
        pagination_books = [
            Book(title=f'P-Book-{i}', language=cls.lang_en)
            for i in range(50)
        ]
        Book.objects.bulk_create(pagination_books)
        # Note: bulk_create doesn't call save() or handle ManyToMany, 
        # but for title-based alphabet/pagination it's enough if we don't need authors/genres for these 50.

    def test_book_list_view_status_code(self):
        """
        Verify the view returns 200 OK and uses the correct template.
        """
        response = self.client.get(reverse('library:book_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'library/book_list.html')

    def test_book_list_view_all_books_default(self):
        """
        Verify all books are shown by default (paged).
        """
        response = self.client.get(reverse('library:book_list'))
        # 3 initial + 50 pagination = 53 total. Paginate by 50.
        self.assertEqual(len(response.context['books']), 50)
        self.assertEqual(response.context['paginator'].count, 53)

    def test_book_list_view_language_filter(self):
        """
        Verify filtering by language.
        """
        response = self.client.get(reverse('library:book_list'), {'lang': ['ru']})
        self.assertEqual(len(response.context['books']), 1)
        self.assertEqual(response.context['books'][0], self.book2)

    def test_book_list_view_genre_filter_with_subgenres(self):
        """
        Verify filtering by genre includes subgenres.
        """
        # Filter by 'fiction' should include 'fiction' (book1) and 'scifi' (book2)
        response = self.client.get(reverse('library:book_list'), {'genre': ['fiction']})
        # book1 and book2 match.
        titles = [b.title for b in response.context['books']]
        self.assertIn('A-Book', titles)
        self.assertIn('B-Book', titles)
        self.assertEqual(len(titles), 2)

    def test_book_list_view_alphabet_filter(self):
        """
        Verify filtering by alphabet prefix.
        """
        response = self.client.get(reverse('library:book_list'), {'filter': 'A'})
        self.assertEqual(len(response.context['books']), 1)
        self.assertEqual(response.context['books'][0], self.book1)

    def test_book_list_view_combined_filter(self):
        """
        Verify combined AND logic for language, genre, and alphabet.
        """
        # lang=en, genre=fiction, filter=A -> matches book1
        response = self.client.get(reverse('library:book_list'), {
            'lang': ['en'],
            'genre': ['fiction'],
            'filter': 'A'
        })
        self.assertEqual(len(response.context['books']), 1)
        self.assertEqual(response.context['books'][0], self.book1)

        # lang=ru, genre=fiction, filter=A -> matches nothing
        response = self.client.get(reverse('library:book_list'), {
            'lang': ['ru'],
            'genre': ['fiction'],
            'filter': 'A'
        })
        self.assertEqual(len(response.context['books']), 0)

    def test_book_list_view_htmx_partial(self):
        """
        Verify HTMX request returns partial fragment.
        """
        response = self.client.get(reverse('library:book_list'), HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 200)
        self.assertIn('library/book_list.html#books_list-result', response.template_name)

    def test_book_list_view_author_string_formatting(self):
        """
        Verify "Title by Author" vs "Title by Author et al.".
        """
        response = self.client.get(reverse('library:book_list'))
        content = response.content.decode()
        
        # Book 1: one author
        self.assertIn('A-Book by Doe, John', content)
        self.assertNotIn('A-Book by Doe, John et al.', content)
        
        # Book 2: two authors
        self.assertIn('B-Book by Doe, John et al.', content)

    def test_book_list_view_pagination_preserves_filters(self):
        """
        Verify pagination links preserve current filters.
        """
        # Create more books with the same filters to trigger pagination
        more_books = [
            Book(title=f'Z-Book-{i}', language=self.lang_en)
            for i in range(60)
        ]
        # We need to add genres to them, so bulk_create is tricky for M2M.
        # Let's just create them normally for this test.
        for b in more_books:
            b.save()
            b.genres.add(self.genre_history)
            
        params = {'genre': ['history'], 'lang': ['en']}
        response = self.client.get(reverse('library:book_list'), params)
        content = response.content.decode()
        
        # Initial 1 (book3) + 60 = 61 books for 'history' & 'en'
        # Page 1 shows 50, Page 2 shows 11.
        
        self.assertIn('page=2', content)
        self.assertIn('genre=history', content)
        self.assertIn('lang=en', content)

    def test_book_list_view_filter_summary_human_readable(self):
        """
        Verify that active filters in summary show human-readable names.
        """
        params = {
            'lang': ['en'],
            'genre': ['fiction'],
            'filter': 'A'
        }
        response = self.client.get(reverse('library:book_list'), params)
        content = response.content.decode()

        # Should show names, not just codes
        self.assertIn('Lang: English', content)
        self.assertIn('Genre: Fiction', content)
        self.assertIn('Title: a', content)  # 'a' is capitalized to 'A' in tree, but find_alphabet_node finds it

        # Test with regex node (e.g. 'other')
        # We need a book starting with non-alpha to trigger 'other' in tree
        Book.objects.create(title='!!!-Book', language=self.lang_en)
        
        # In get_alphabet_tree, other_node entries include regex=r'^[^[:alpha:][:digit:]]'
        params = {'regex': r'^[^[:alpha:][:digit:]]'}
        response = self.client.get(reverse('library:book_list'), params)
        content = response.content.decode()
        self.assertIn('Title: * (all non-alpha)', content)

