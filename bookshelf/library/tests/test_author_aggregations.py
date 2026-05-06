from bookshelf.tests.base_test import BaseTestCase
from library.models import Author, Book, Language, Genre
from library.services import get_author_languages, get_author_genres_tree

class AuthorAggregationsTest(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author_a = Author.objects.create(first_name='Author', last_name='A')
        cls.author_b = Author.objects.create(first_name='Author', last_name='B')
        cls.lang_en = Language.objects.create(code='en', name='English')
        cls.lang_uk = Language.objects.create(code='uk', name='Ukrainian')

    def test_get_author_languages_empty(self):
        """Author with 0 books -> returns empty queryset."""
        langs = get_author_languages(self.author_a)
        self.assertEqual(langs.count(), 0)

    def test_get_author_languages_single(self):
        """Author with 2 books in 'en' -> returns 1 language ('en') with book_count=2."""
        b1 = Book.objects.create(title='B1', language=self.lang_en)
        b1.authors.add(self.author_a)
        b2 = Book.objects.create(title='B2', language=self.lang_en)
        b2.authors.add(self.author_a)

        langs = get_author_languages(self.author_a)
        self.assertEqual(langs.count(), 1)
        self.assertEqual(langs[0].code, 'en')
        self.assertEqual(langs[0].book_count, 2)

    def test_get_author_languages_multiple(self):
        """Author with 1 book in 'en', 2 in 'uk' -> returns sorted languages ('en', 'uk') with correct counts."""
        b1 = Book.objects.create(title='B1', language=self.lang_en)
        b1.authors.add(self.author_a)
        b2 = Book.objects.create(title='B2', language=self.lang_uk)
        b2.authors.add(self.author_a)
        b3 = Book.objects.create(title='B3', language=self.lang_uk)
        b3.authors.add(self.author_a)

        langs = get_author_languages(self.author_a)
        self.assertEqual(langs.count(), 2)
        # Sorted by name ('English' < 'Ukrainian')
        self.assertEqual(langs[0].code, 'en')
        self.assertEqual(langs[0].book_count, 1)
        self.assertEqual(langs[1].code, 'uk')
        self.assertEqual(langs[1].book_count, 2)

    def test_get_author_languages_isolation(self):
        """Author A has 1 book in 'en'. Author B has 1 book in 'en'. get_author_languages(Author A) -> returns 'en' with book_count=1."""
        b1 = Book.objects.create(title='Shared', language=self.lang_en)
        b1.authors.add(self.author_a, self.author_b)

        b2 = Book.objects.create(title='Only B', language=self.lang_en)
        b2.authors.add(self.author_b)

        langs_a = get_author_languages(self.author_a)
        self.assertEqual(langs_a.get(code='en').book_count, 1)

        langs_b = get_author_languages(self.author_b)
        self.assertEqual(langs_b.get(code='en').book_count, 2)

    def test_get_author_genres_tree_empty(self):
        """Author with 0 books -> returns empty list."""
        tree = get_author_genres_tree(self.author_a)
        self.assertEqual(tree, [])

    def test_get_author_genres_tree_hierarchy(self):
        """Author has book in 'Sub-genre' (parent: 'Parent-genre'). Tree should contain 'Parent-genre' with 'Sub-genre' as child."""
        g_parent = Genre.objects.create(name='Parent-genre', code='p')
        g_sub = Genre.objects.create(name='Sub-genre', code='s', parent=g_parent)

        b1 = Book.objects.create(title='B1', language=self.lang_en)
        b1.authors.add(self.author_a)
        b1.genres.add(g_sub)

        tree = get_author_genres_tree(self.author_a)
        self.assertEqual(len(tree), 1)
        self.assertEqual(tree[0]['genre'], g_parent)
        self.assertEqual(len(tree[0]['children']), 1)
        self.assertEqual(tree[0]['children'][0]['genre'], g_sub)

    def test_get_author_genres_tree_counts(self):
        """Book in 'Sub-genre' (count 1). Book in 'Parent-genre' (count 1)."""
        g_parent = Genre.objects.create(name='Parent-genre', code='p')
        g_sub = Genre.objects.create(name='Sub-genre', code='s', parent=g_parent)

        b1 = Book.objects.create(title='B1', language=self.lang_en)
        b1.authors.add(self.author_a)
        b1.genres.add(g_sub)

        b2 = Book.objects.create(title='B2', language=self.lang_en)
        b2.authors.add(self.author_a)
        b2.genres.add(g_parent)

        tree = get_author_genres_tree(self.author_a)
        self.assertEqual(tree[0]['book_count'], 1)
        self.assertEqual(tree[0]['children'][0]['book_count'], 1)

    def test_get_author_genres_tree_several_books_count(self):
        """
        Several Books Count:
        Genres: P1 with children S1, S2; P2 with child S3.
        Books: 2 in S1; 5 in S2; 1 in (S1, S2); 1 in (S1, S3).
        Expected: S1=4, S2=6, S3=1, P1=0, P2=0.
        """
        p1 = Genre.objects.create(name='Parent 1', code='p1')
        s1 = Genre.objects.create(name='Sub 1', code='s1', parent=p1)
        s2 = Genre.objects.create(name='Sub 2', code='s2', parent=p1)
        p2 = Genre.objects.create(name='Parent 2', code='p2')
        s3 = Genre.objects.create(name='Sub 3', code='s3', parent=p2)

        # 2 books in S1
        for i in range(2):
            b = Book.objects.create(title=f'S1_{i}', language=self.lang_en)
            b.authors.add(self.author_a)
            b.genres.add(s1)
        
        # 5 books in S2
        for i in range(5):
            b = Book.objects.create(title=f'S2_{i}', language=self.lang_en)
            b.authors.add(self.author_a)
            b.genres.add(s2)

        # 1 book in (S1, S2)
        b_shared_12 = Book.objects.create(title='Shared 1-2', language=self.lang_en)
        b_shared_12.authors.add(self.author_a)
        b_shared_12.genres.add(s1, s2)

        # 1 book in (S1, S3)
        b_shared_13 = Book.objects.create(title='Shared 1-3', language=self.lang_en)
        b_shared_13.authors.add(self.author_a)
        b_shared_13.genres.add(s1, s3)

        tree = get_author_genres_tree(self.author_a)
        
        # Find P1 and P2 in tree
        p1_node = next(n for n in tree if n['genre'] == p1)
        p2_node = next(n for n in tree if n['genre'] == p2)

        self.assertEqual(p1_node['book_count'], 0)
        self.assertEqual(p2_node['book_count'], 0)

        s1_node = next(n for n in p1_node['children'] if n['genre'] == s1)
        s2_node = next(n for n in p1_node['children'] if n['genre'] == s2)
        s3_node = next(n for n in p2_node['children'] if n['genre'] == s3)

        self.assertEqual(s1_node['book_count'], 4)
        self.assertEqual(s2_node['book_count'], 6)
        self.assertEqual(s3_node['book_count'], 1)

    def test_get_author_genres_tree_sorting(self):
        """Root level sorted ['A', 'B', 'C']. Children of 'B' sorted ['ba', 'bb']. Case-insensitive."""
        ga = Genre.objects.create(name='A', code='a')
        gb = Genre.objects.create(name='B', code='b')
        gc = Genre.objects.create(name='C', code='c')
        
        gba = Genre.objects.create(name='ba', code='ba', parent=gb)
        gbb = Genre.objects.create(name='BB', code='bb', parent=gb) # Test case insensitivity

        for g in [ga, gba, gbb, gc]:
            b = Book.objects.create(title=f'Book_{g.code}', language=self.lang_en)
            b.authors.add(self.author_a)
            b.genres.add(g)

        tree = get_author_genres_tree(self.author_a)
        
        self.assertEqual(len(tree), 3)
        self.assertEqual(tree[0]['genre'].name, 'A')
        self.assertEqual(tree[1]['genre'].name, 'B')
        self.assertEqual(tree[2]['genre'].name, 'C')

        b_children = tree[1]['children']
        self.assertEqual(len(b_children), 2)
        self.assertEqual(b_children[0]['genre'].name, 'ba')
        self.assertEqual(b_children[1]['genre'].name, 'BB')

    def test_get_author_genres_tree_isolation(self):
        """Author A has a book in 'Sci-Fi'. Author B has a book in 'Sci-Fi'. get_author_genres_tree(Author A) -> 'Sci-Fi' node has book_count=1."""
        g_sci = Genre.objects.create(name='Sci-Fi', code='sci')

        b1 = Book.objects.create(title='A1', language=self.lang_en)
        b1.authors.add(self.author_a)
        b1.genres.add(g_sci)

        b2 = Book.objects.create(title='B1', language=self.lang_en)
        b2.authors.add(self.author_b)
        b2.genres.add(g_sci)

        tree_a = get_author_genres_tree(self.author_a)
        self.assertEqual(tree_a[0]['book_count'], 1)

        tree_b = get_author_genres_tree(self.author_b)
        self.assertEqual(tree_b[0]['book_count'], 1)

    def test_get_author_genres_tree_missing_genre_in_all_genres(self):
        """
        Test that get_author_genres_tree handles genres that are in direct_genres_qs but missing from all_genres.
        This is a defensive edge case.
        """
        from unittest.mock import patch, MagicMock
        
        # Create a real genre and book
        g_real = Genre.objects.create(name='Real', code='real')
        b1 = Book.objects.create(title='B1', language=self.lang_en)
        b1.authors.add(self.author_a)
        b1.genres.add(g_real)
        
        # we need a real object that has 'id' and 'book_count' and 'parent_id'
        class MockGenre:
            def __init__(self, id, book_count, parent_id=None):
                self.id = id
                self.book_count = book_count
                self.parent_id = parent_id

        real_genre_with_count = MockGenre(id=g_real.id, book_count=1)
        fake_genre = MockGenre(id=9999, book_count=1)
        
        # direct_genres_qs is what filter().annotate().distinct() returns
        mock_qs = MagicMock()
        mock_qs.exists.return_value = True
        mock_qs.__iter__.return_value = iter([real_genre_with_count, fake_genre])
        
        # Mock chaining
        mock_qs.annotate.return_value = mock_qs
        mock_qs.distinct.return_value = mock_qs

        with patch('library.services.Genre.objects.filter', return_value=mock_qs):
            # Genre.objects.all() will only include the real genre in its return value
            # which get_author_genres_tree uses to build all_genres mapping
            with patch('library.services.Genre.objects.all', return_value=[g_real]):
                tree = get_author_genres_tree(self.author_a)
                
                # Should only have the real genre in the tree
                self.assertEqual(len(tree), 1)
                self.assertEqual(tree[0]['genre'].id, g_real.id)
                self.assertEqual(tree[0]['book_count'], 1)
