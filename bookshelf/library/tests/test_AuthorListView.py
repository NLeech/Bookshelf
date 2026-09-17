import re

from django.urls import reverse
from parameterized import parameterized

from bookshelf.tests.base_test import BaseTestCase
from library.models import Author
from library.services import AlphabetTree


class AuthorListViewTests(BaseTestCase):
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

    def test_author_list_view_pagination_links_preserve_params(self):
        """
        Verify that pagination links correctly include filter and regex parameters.
        """
        # We need more than 50 authors with the same filter to trigger pagination
        Author.objects.bulk_create([
            Author(first_name=f'F{i}', last_name='Z-Author') for i in range(60)
        ])
        
        params = {'filter': 'Z', 'regex': '^Z'}
        response = self.client.get(reverse('library:authors_list'), params)
        content = response.content.decode()
        
        # Check Next link
        self.assertIn('page=2', content)
        self.assertIn('filter=Z', content)
        self.assertIn('regex=%5EZ', content)  # ^ is URL encoded as %5E
        
        # Check Jump to Page form
        self.assertIn('name="filter" value="Z"', content)
        self.assertIn('name="regex" value="^Z"', content)

    def test_author_list_view_active_alphabet_node_context(self):
        """
        Verify active_alphabet_node is absent when unfiltered and resolves to the
        matching tree node when a filter is applied.
        """
        # Arrange / Act: unfiltered request
        response = self.client.get(reverse('library:authors_list'))

        # Assert: nothing is active, so the key is not added at all
        self.assertNotIn('active_alphabet_node', response.context)

        # Arrange / Act: filtered request; 'l' is a root node for the 50 'Last{i}' authors
        response = self.client.get(reverse('library:authors_list'), {'filter': 'l'})

        # Assert
        node = response.context['active_alphabet_node']
        self.assertIsInstance(node, AlphabetTree)
        self.assertEqual(node.name, 'l')

    @parameterized.expand([
        ('matched_prefix', {'filter': 'l'}, 'Last name: L'),
        ('matched_regex', {'regex': r'^([^[:alpha:][:digit:]]|a|b)'}, 'Last name: Other'),
        ('unmatched_prefix', {'filter': 'XYZ'}, 'Last name: Xyz'),
        ('unmatched_regex', {'regex': '^zzz'}, 'Last name: Other'),
    ])
    def test_author_list_view_filter_summary_parameterized(self, _name, params, expected_badge):
        """
        Verify the filter summary badge always reads `Last name: <label>`: the node name
        when the tree resolves the selection, and a readable derived label when it does not.
        """
        # Act
        response = self.client.get(reverse('library:authors_list'), params)
        content = response.content.decode()

        # Assert
        self.assertIn('Active Filters:', content)
        self.assertIn(expected_badge, content)

    def test_author_list_view_no_filter_summary_when_unfiltered(self):
        """
        Verify an unfiltered request renders no filter summary and no clear control.
        """
        # Act
        response = self.client.get(reverse('library:authors_list'))
        content = response.content.decode()

        # Assert
        self.assertNotIn('Active Filters:', content)
        self.assertNotIn('Clear all', content)

    def test_author_list_view_clear_button_attributes(self):
        """
        Verify the clear control keeps a plain href and carries the HTMX attributes
        that swap the author list wrapper.
        """
        # Act
        url = reverse('library:authors_list')
        response = self.client.get(url, {'filter': 'l'})
        content = response.content.decode()

        # Assert: inspect the clear anchor itself, not the page as a whole
        match = re.search(r'<a[^>]*>Clear all</a>', content)
        self.assertIsNotNone(match, 'Clear all control not found')
        anchor = match.group(0)

        self.assertIn(f'href="{url}"', anchor)
        self.assertIn(f'hx-get="{url}"', anchor)
        self.assertIn('hx-target="#authors_list"', anchor)
        self.assertIn('hx-swap="innerHTML"', anchor)
        self.assertIn('hx-push-url="true"', anchor)

    def test_author_list_view_has_no_group_clear_buttons(self):
        """
        Verify the author page renders only `Clear all`: it passes no
        group_clear_target, so the shared summary adds no per-group controls.
        """
        # Act
        response = self.client.get(reverse('library:authors_list'), {'filter': 'l'})
        content = response.content.decode()

        # Assert
        self.assertIn('Clear all', content)
        self.assertNotIn('id="clear-langs"', content)
        self.assertNotIn('id="clear-genres"', content)
        self.assertNotIn('id="clear-node"', content)

    def test_author_list_view_alphabet_tree_targets_list_wrapper(self):
        """
        Verify alphabet tree buttons target #authors_list, the wrapper that now holds
        both the filter summary and the author list.
        """
        # Act
        url = reverse('library:authors_list')
        response = self.client.get(url)
        content = response.content.decode()

        # Assert: find the tree button for the 'l' node and check its target
        buttons = [
            tag for tag in re.findall(r'<button[^>]*>', content)
            if f'hx-get="{url}?filter=l"' in tag
        ]
        self.assertTrue(buttons, 'Alphabet tree button for node "l" not found')
        for button in buttons:
            self.assertIn('hx-target="#authors_list"', button)

    def test_author_list_view_htmx_partial_updates_summary_and_list(self):
        """
        Verify one HTMX request returns both the filter summary and the author list,
        without the base layout.
        """
        # Act
        response = self.client.get(
            reverse('library:authors_list'),
            {'filter': 'l'},
            HTTP_HX_REQUEST='true'
        )
        content = response.content.decode()

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertIn('Last name: L', content)
        self.assertIn('Clear all', content)
        self.assertIn('<li class="py-1 border-bottom">', content)
        self.assertNotIn('<html', content)
