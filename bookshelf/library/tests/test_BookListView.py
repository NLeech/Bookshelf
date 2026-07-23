import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from parameterized import parameterized

from bookshelf.tests.base_test import BaseTestCase
from library.models import Author, Book, Language, Genre
from library.services import AlphabetTree

User = get_user_model()


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
        # Filter by 'fiction' AND 'scifi' (simulating frontend behavior)
        response = self.client.get(reverse('library:book_list'), {'genre': ['fiction', 'scifi']})
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

    def test_book_list_clear_link_is_not_htmx(self):
        """
        Verify the book page clear control stays a plain full page link after the
        filter summary was extracted into a shared partial.
        """
        # Act
        url = reverse('library:book_list')
        response = self.client.get(url, {'filter': 'A'})
        content = response.content.decode()

        # Assert: inspect the clear anchor itself. The page-wide check would be
        # wrong here: the sidebar #filter-form legitimately carries hx-get="/books/".
        match = re.search(r'<a[^>]*>Clear all</a>', content)
        self.assertIsNotNone(match, 'Clear all control not found')
        anchor = match.group(0)

        self.assertIn(f'href="{url}"', anchor)
        self.assertNotIn('hx-', anchor)

    def test_alphabet_tree_oob_update(self):
        """
        Verify HTMX request returns OOB swap for alphabet tree when filters change.
        """
        response = self.client.get(
            reverse('library:book_list'), 
            {'lang': ['ru']}, 
            HTTP_HX_REQUEST='true',
            HTTP_HX_TRIGGER='filter-form'
        )
        self.assertEqual(response.status_code, 200)

        content = response.content.decode()
        # Should have the OOB fragment
        self.assertIn('id="alphabet-tree-sidebar"', content)
        self.assertIn('hx-swap-oob="true"', content)

        # Check counts in the tree (partial)
        self.assertIn('B (1)', content)

    def test_alphabet_tree_no_oob_on_tree_click(self):
        """
        Verify HTMX request from Alphabet Tree does NOT return itself.
        """
        # Simulate click on letter 'B'
        response = self.client.get(
            reverse('library:book_list'), 
            {'filter': 'B'}, 
            HTTP_HX_REQUEST='true'
            # HX-Trigger is missing or different
        )
        self.assertEqual(response.status_code, 200)

        content = response.content.decode()
        self.assertNotIn('id="alphabet-tree-sidebar"', content)

    # --- Per-group Clear controls -------------------------------------------------

    #: Ids of every region that can be sent as an out-of-band fragment.
    OOB_REGION_IDS = (
        'alphabet-tree-sidebar',
        'languages-filter',
        'genres-filter',
        'filter-form-state',
    )

    @staticmethod
    def _tag_by_id(content, element_id):
        """Return the opening tag carrying ``id="<element_id>"``, or None."""
        match = re.search(rf'<a[^>]*id="{element_id}"[^>]*>', content)
        return match.group(0) if match else None

    @staticmethod
    def _attr(tag, name):
        """Return the value of an attribute of an already extracted tag."""
        match = re.search(rf'{re.escape(name)}="([^"]*)"', tag)
        return match.group(1) if match else None

    @parameterized.expand([
        ('langs', 'clear-langs', ['lang='], ['genre=fiction', 'filter=A']),
        ('genres', 'clear-genres', ['genre='], ['lang=en', 'filter=A']),
        ('node', 'clear-node', ['filter=', 'regex='], ['lang=en', 'genre=fiction']),
    ])
    def test_book_list_group_clear_urls_parameterized(self, _name, control_id, gone, kept):
        """Each group Clear drops its own parameters and `page`, and keeps the rest."""
        # Arrange / Act
        response = self.client.get(reverse('library:book_list'), {
            'lang': ['en'],
            'genre': ['fiction'],
            'filter': 'A',
            'page': 1,
        })
        tag = self._tag_by_id(response.content.decode(), control_id)

        # Assert
        self.assertIsNotNone(tag, f'Control {control_id} not found')
        href = self._attr(tag, 'href')
        for fragment in gone:
            self.assertNotIn(fragment, href)
        for fragment in kept:
            self.assertIn(fragment, href)
        self.assertNotIn('page=', href)
        self.assertEqual(self._attr(tag, 'hx-get'), href)

    @parameterized.expand([
        ('langs', 'clear-langs'),
        ('genres', 'clear-genres'),
        ('node', 'clear-node'),
    ])
    def test_book_list_group_clear_htmx_attributes_parameterized(self, _name, control_id):
        """Each group Clear swaps the book list wrapper in place and pushes the URL."""
        # Arrange / Act
        response = self.client.get(reverse('library:book_list'), {
            'lang': ['en'],
            'genre': ['fiction'],
            'filter': 'A',
        })
        tag = self._tag_by_id(response.content.decode(), control_id)

        # Assert
        self.assertIsNotNone(tag, f'Control {control_id} not found')
        self.assertIn('hx-target="#books_list-result"', tag)
        self.assertIn('hx-swap="innerHTML"', tag)
        self.assertIn('hx-push-url="true"', tag)

    @parameterized.expand([
        ('lang_only', {'lang': ['en']}, ['clear-langs']),
        ('genre_only', {'genre': ['fiction']}, ['clear-genres']),
        ('title_only', {'filter': 'A'}, ['clear-node']),
        ('regex_only', {'regex': '^A'}, ['clear-node']),
        ('unfiltered', {}, []),
    ])
    def test_book_list_group_clear_rendered_only_for_active_groups_parameterized(
        self, _name, params, expected_ids
    ):
        """A group Clear renders only when its own filter group is active."""
        # Arrange / Act
        response = self.client.get(reverse('library:book_list'), params)
        content = response.content.decode()

        # Assert
        for control_id in ('clear-langs', 'clear-genres', 'clear-node'):
            if control_id in expected_ids:
                self.assertIn(f'id="{control_id}"', content)
            else:
                self.assertNotIn(f'id="{control_id}"', content)

    def test_book_list_clear_all_link_unchanged(self):
        """`Clear all` stays a plain full page link next to the new group controls."""
        # Arrange / Act
        url = reverse('library:book_list')
        response = self.client.get(url, {
            'lang': ['en'],
            'genre': ['fiction'],
            'filter': 'A',
        })
        content = response.content.decode()

        # Assert: the group controls are rendered in the same response
        self.assertIn('id="clear-langs"', content)

        match = re.search(r'<a[^>]*>Clear all</a>', content)
        self.assertIsNotNone(match, 'Clear all control not found')
        anchor = match.group(0)
        self.assertIn(f'href="{url}"', anchor)
        self.assertNotIn('hx-', anchor)

    @parameterized.expand([
        ('filter_form', {'lang': ['ru']}, 'filter-form', ['alphabet-tree-sidebar']),
        ('tree_click', {'filter': 'B'}, None, ['filter-form-state']),
        (
            'clear_langs',
            {'genre': ['fiction'], 'filter': 'A'},
            'clear-langs',
            ['languages-filter', 'alphabet-tree-sidebar'],
        ),
        (
            'clear_genres',
            {'lang': ['en'], 'filter': 'A'},
            'clear-genres',
            ['genres-filter', 'alphabet-tree-sidebar'],
        ),
        ('clear_node', {'lang': ['en'], 'genre': ['fiction']}, 'clear-node', ['filter-form-state']),
        ('unknown_trigger', {'filter': 'B'}, 'some-other-id', ['filter-form-state']),
    ])
    def test_book_list_oob_fragment_matrix_parameterized(
        self, _name, params, trigger, expected_ids
    ):
        """Each HTMX trigger returns exactly the out-of-band fragments it needs."""
        # Arrange
        headers = {'HTTP_HX_REQUEST': 'true'}
        if trigger is not None:
            headers['HTTP_HX_TRIGGER'] = trigger

        # Act
        response = self.client.get(reverse('library:book_list'), params, **headers)
        content = response.content.decode()

        # Assert
        self.assertEqual(response.status_code, 200)
        for region_id in self.OOB_REGION_IDS:
            if region_id in expected_ids:
                self.assertIn(f'id="{region_id}"', content)
            else:
                self.assertNotIn(f'id="{region_id}"', content)
        self.assertNotIn('<html', content)

    @parameterized.expand([
        ('langs', {'genre': ['fiction'], 'filter': 'A'}, 'clear-langs', ['Genre: Fiction'], 'lang'),
        ('genres', {'lang': ['en'], 'filter': 'A'}, 'clear-genres', ['Lang: English'], 'genre'),
        (
            'node',
            {'lang': ['en'], 'genre': ['fiction']},
            'clear-node',
            ['Lang: English', 'Genre: Fiction'],
            None,
        ),
    ])
    def test_book_list_clear_keeps_other_filters_parameterized(
        self, _name, params, trigger, surviving_badges, cleared_input_name
    ):
        """Clearing one group re-renders it empty and leaves the other groups applied."""
        # Arrange / Act
        response = self.client.get(
            reverse('library:book_list'),
            params,
            HTTP_HX_REQUEST='true',
            HTTP_HX_TRIGGER=trigger,
        )
        content = response.content.decode()

        # Assert: the other groups still show their badges
        for badge in surviving_badges:
            self.assertIn(badge, content)

        if cleared_input_name is not None:
            inputs = re.findall(rf'<input[^>]*name="{cleared_input_name}"[^>]*>', content)
            self.assertTrue(inputs, f'No {cleared_input_name} inputs returned')
            for tag in inputs:
                self.assertNotIn('checked', tag)
        else:
            # The alphabet group clears through the hidden form state instead
            match = re.search(r'<div id="filter-form-state"[^>]*>(.*?)</div>', content, re.DOTALL)
            self.assertIsNotNone(match, 'filter-form-state fragment not returned')
            self.assertNotIn('name="filter"', match.group(1))
            self.assertNotIn('name="regex"', match.group(1))

    def test_book_list_alphabet_tree_oob_urls_are_absolute(self):
        """Tree buttons in the OOB fragment keep the book list path, not a bare `?filter=`."""
        # Arrange / Act
        url = reverse('library:book_list')
        response = self.client.get(
            url,
            {'lang': ['ru']},
            HTTP_HX_REQUEST='true',
            HTTP_HX_TRIGGER='filter-form',
        )
        content = response.content.decode()

        # Assert: the OOB fragment opens the response, and the tree buttons are the
        # only buttons in it that carry hx-get
        marker = content.find('id="alphabet-tree-sidebar"')
        self.assertNotEqual(marker, -1, 'Alphabet tree OOB fragment not returned')
        hx_gets = re.findall(r'<button[^>]*hx-get="([^"]*)"', content[marker:])
        self.assertTrue(hx_gets, 'No alphabet tree buttons in the OOB fragment')
        for hx_get in hx_gets:
            self.assertTrue(
                hx_get.startswith(url),
                f'Tree button URL {hx_get!r} does not start with {url!r}'
            )

    def test_book_list_full_page_renders_each_oob_region_once(self):
        """A normal page load renders every out-of-band region exactly once."""
        # Arrange / Act
        response = self.client.get(reverse('library:book_list'))
        content = response.content.decode()

        # Assert
        for region_id in self.OOB_REGION_IDS:
            self.assertEqual(
                content.count(f'id="{region_id}"'),
                1,
                f'Region {region_id} is not rendered exactly once'
            )

    def test_alphabet_tree_respects_genre(self):
        """
        Verify alphabet tree counts and nodes respect active genre filter.
        """
        # Filter by history -> only book3 (Title: C-Book) matches
        response = self.client.get(reverse('library:book_list'), {'genre': ['history']})
        content = response.content.decode()

        # Only 'C' should have a count
        self.assertIn('C (1)', content)
        self.assertNotIn('A (1)', content)
        self.assertNotIn('B (1)', content)

        # Filter by fiction AND subgenre scifi (simulating frontend behavior)
        # book1 (A-Book) is fiction, book2 (B-Book) is scifi
        response = self.client.get(reverse('library:book_list'), {'genre': ['fiction', 'scifi']})
        content = response.content.decode()
        self.assertIn('A (1)', content)
        self.assertIn('B (1)', content)
        self.assertNotIn('C (1)', content)


class BookListViewCanViewBookTests(BaseTestCase):
    """Tests that BookListView exposes ``can_view_book`` and the book card
    toggles Read/Preview based on the user's configured book-view permission
    (``settings.VIEW_BOOK_PERM``).
    """

    @classmethod
    def setUpTestData(cls):
        cls.lang_en = Language.objects.create(code='en', name='English')
        cls.book = Book.objects.create(title='A-Book', language=cls.lang_en)

        cls.user_no_access = User.objects.create_user(
            username='no_access', email='no_access@example.com', password='password'
        )
        cls.user_with_access = User.objects.create_user(
            username='with_access', email='with_access@example.com', password='password'
        )
        # Grant whatever permission the configured codename points to, so the
        # test follows ``settings.VIEW_BOOK_PERM`` rather than a hardcoded
        # literal.
        app_label, codename = settings.VIEW_BOOK_PERM.split('.')
        perm = Permission.objects.get(
            content_type__app_label=app_label, codename=codename
        )
        cls.user_with_access.user_permissions.add(perm)

    @parameterized.expand([
        ('with_perm', 'with_access', True, '</i> Read', '</i> Preview'),
        ('without_perm', 'no_access', False, '</i> Preview', '</i> Read'),
    ])
    def test_can_view_book_context_and_card_label(
        self, _name, username, expected_flag, expected_label, absent_label
    ):
        """The view exposes the correct ``can_view_book`` flag and the card
        shows Read for permitted users and Preview otherwise.
        """
        self.client.login(username=username, password='password')
        response = self.client.get(reverse('library:book_list'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['can_view_book'], expected_flag)
        self.assertContains(response, expected_label)
        self.assertNotContains(response, absent_label)

