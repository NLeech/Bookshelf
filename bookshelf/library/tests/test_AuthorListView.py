from django.test import TestCase, override_settings
from django.urls import reverse
from django.conf import settings
from parameterized import parameterized

from library.models import Author
from library.services import AlphabetTree


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class AuthorListViewTests(TestCase):
    """
    Tests for the AuthorListView in library.views.
    """

    @classmethod
    def setUpTestData(cls):
        # Create some authors for filtering and pagination tests
        cls.author_a = Author.objects.create(first_name='John', last_name='Adam')
        cls.author_b = Author.objects.create(first_name='Jane', last_name='Bert')
        
        # Create authors for pagination (PAGINATE_BY is 50)
        # Total authors will be 2 + 50 = 52
        pagination_authors = [
            Author(first_name=f'First{i}', last_name=f'Last{i}') 
            for i in range(50)
        ]
        Author.objects.bulk_create(pagination_authors)

    def test_author_list_view_status_code(self):
        """
        Verify the view returns 200 OK and uses the correct template.
        """
        response = self.client.get(reverse('library:authors_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'library/author_list.html')

    def test_author_list_view_pagination(self):
        """
        Verify pagination works correctly (showing 50 authors per page).
        """
        response = self.client.get(reverse('library:authors_list'))
        self.assertEqual(len(response.context['authors']), 50)
        self.assertTrue(response.context['is_paginated'])
        self.assertEqual(response.context['paginator'].count, 52)

    @parameterized.expand([
        ('startswith_lower', {'filter': 'a'}, 'Adam', 'Bert'),
        ('startswith_upper', {'filter': 'A'}, 'Adam', 'Bert'),
        ('regex_lower', {'regex': '^b'}, 'Bert', 'Adam'),
        ('regex_upper', {'regex': '^B'}, 'Bert', 'Adam'),
        ('regex_precedence', {'filter': 'A', 'regex': '^B'}, 'Bert', 'Adam'),
    ])
    def test_author_list_view_filtering_parameterized(self, name, params, expected, not_expected):
        """
        Verify filtering logic (startswith, regex, case insensitivity, precedence).
        """
        response = self.client.get(reverse('library:authors_list'), params)
        content = response.content.decode()
        self.assertIn(expected, content)
        self.assertNotIn(not_expected, content)

    def test_author_list_view_empty_results(self):
        """
        Verify "No authors found." message when no authors match filter.
        """
        response = self.client.get(reverse('library:authors_list'), {'filter': 'XYZ'})
        self.assertIn('No authors found.', response.content.decode())
        self.assertEqual(len(response.context['authors']), 0)

    def test_author_list_view_htmx_partial(self):
        """
        Verify that an HTMX request returns only the partial template fragment.
        """
        response = self.client.get(reverse('library:authors_list'), HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 200)
        # In Django 6, the template_name will be updated with the block name
        self.assertIn('library/author_list.html#authors_list-result', response.template_name)

    def test_author_list_view_context(self):
        """
        Verify that filter and regex match query parameters in context.
        """
        params = {'filter': 'A', 'regex': '^A'}
        response = self.client.get(reverse('library:authors_list'), params)
        self.assertEqual(response.context['filter'], 'A')
        self.assertEqual(response.context['regex'], '^A')

    def test_author_list_view_alphabet_tree_integration(self):
        """
        Verify that alphabet_tree is in context and contains expected nodes.
        """
        # We created 'Adam', 'Bert', and 'Last0'...'Last49'
        # 'Adam' -> 'a', 'Bert' -> 'b', 'Last' -> 'l'
        # With 52 authors total, alphabet_tree nodes for a, b, l should be present.
        response = self.client.get(reverse('library:authors_list'))
        self.assertIn('alphabet_tree', response.context)
        tree = response.context['alphabet_tree']
        self.assertIsInstance(tree, AlphabetTree)
        
        node_names = [e.name for e in tree.entries]
        # Since min_first_level_quantity defaults to 10 in get_alphabet_tree, 
        # 'a' and 'b' (1 author each) will be in 'other'.
        # 'l' (50 authors) will be at root.
        self.assertIn('l', node_names)
        self.assertIn('other', node_names)
        
        other_node = next(e for e in tree.entries if e.name == 'other')
        other_child_names = [e.name for e in other_node.entries]
        self.assertIn('a', other_child_names)
        self.assertIn('b', other_child_names)
