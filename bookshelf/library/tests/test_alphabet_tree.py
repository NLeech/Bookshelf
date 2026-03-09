from django.test import TestCase
from library.models import Author
from library.sevices import get_alphabet_tree
from parameterized import parameterized

class GetAlphabetTreeTest(TestCase):
    """
    Tests for the get_alphabet_tree function.
    """

    def test_empty_database(self):
        """
        Test that an empty database returns a root with no entries.
        """
        root = get_alphabet_tree()
        self.assertEqual(len(root.entries), 0)

    def test_basic_categorization(self):
        """
        Test that authors are correctly categorized into alpha, digit, and other.
        Use min_first_level_quantity=1 to keep alpha nodes at root.
        """
        Author.objects.create(last_name='Abbott')
        Author.objects.create(last_name='123')
        Author.objects.create(last_name='!@#')
        
        root = get_alphabet_tree(min_first_level_quantity=1)
        names = [e.name for e in root.entries]
        
        self.assertIn('a', names)
        self.assertIn('0-9', names)
        self.assertIn('other', names)
        
        a_node = next(e for e in root.entries if e.name == 'a')
        self.assertEqual(a_node.authors_quantity, 1)
        self.assertEqual(str(a_node), 'A')
        
        digit_node = next(e for e in root.entries if e.name == '0-9')
        self.assertEqual(digit_node.authors_quantity, 1)
        
        other_node = next(e for e in root.entries if e.name == 'other')
        self.assertEqual(len(other_node.entries), 1)
        self.assertEqual(other_node.entries[0].name, '* (all non-alpha last names)')

    def test_low_quantity_alpha_moved_to_other(self):
        """
        Test that alpha nodes with quantity < min_first_level_quantity are moved to 'other'.
        """
        Author.objects.create(last_name='Abbott') # 1 'a'
        Author.objects.create(last_name='Zebra')  # 1 'z'
        
        # min_first_level_quantity=2 should move both to 'other'
        root = get_alphabet_tree(min_first_level_quantity=2)
        
        # Root should only contain 'other' (since no high-quantity nodes)
        names = [e.name for e in root.entries]
        self.assertEqual(names, ['other'])
        
        other_node = root.entries[0]
        child_names = [e.name for e in other_node.entries]
        self.assertIn('a', child_names)
        self.assertIn('z', child_names)

    def test_digits_always_at_root(self):
        """
        Test that '0-9' node stays at root even with low quantity.
        """
        Author.objects.create(last_name='123')
        
        root = get_alphabet_tree(min_first_level_quantity=10)
        names = [e.name for e in root.entries]
        self.assertIn('0-9', names)

    def test_case_insensitivity(self):
        """
        Test that the grouping is case-insensitive.
        """
        Author.objects.create(last_name='Abbott')
        Author.objects.create(last_name='abbott')
        
        root = get_alphabet_tree(min_first_level_quantity=1)
        self.assertEqual(root.entries[0].name, 'a')
        self.assertEqual(root.entries[0].authors_quantity, 2)

    @parameterized.expand([
        (2, 5, 2, True),  # min_quantity=2, expect expansion for 'aa' (3 authors)
        (5, 5, 0, False), # min_quantity=5, expect no expansion
    ])
    def test_expansion_threshold(self, min_quantity, total_authors, expected_entries, should_expand):
        """
        Test that expansion only occurs when the number of authors exceeds min_quantity.
        """
        authors = [Author(last_name=f'Aaron{i}') for i in range(total_authors)]
        Author.objects.bulk_create(authors)
        
        root = get_alphabet_tree(min_quantity=min_quantity, min_first_level_quantity=1)
        a_node = next(e for e in root.entries if e.name == 'a')
        
        if should_expand:
            self.assertGreater(len(a_node.entries), 0)
            aa_node = next(e for e in a_node.entries if e.name == 'aa')
            self.assertEqual(aa_node.authors_quantity, total_authors)
        else:
            self.assertEqual(len(a_node.entries), 0)

    def test_multi_level_expansion(self):
        """
        Test expansion up to level 3.
        """
        authors = [
            Author(last_name='Aaa1'),
            Author(last_name='Aaa2'),
            Author(last_name='Aaa3'),
        ]
        Author.objects.bulk_create(authors)
        
        root = get_alphabet_tree(max_tree_depth=3, min_quantity=2, min_first_level_quantity=1)
        
        a_node = next(e for e in root.entries if e.name == 'a')
        self.assertGreater(len(a_node.entries), 0)
        
        aa_node = next(e for e in a_node.entries if e.name == 'aa')
        self.assertGreater(len(aa_node.entries), 0)
        
        aaa_node = next(e for e in aa_node.entries if e.name == 'aaa')
        self.assertEqual(aaa_node.authors_quantity, 3)

    def test_star_nodes(self):
        """
        Test that 'star' nodes are correctly created for non-alpha or short names.
        """
        Author.objects.create(last_name='Ab')     # Contributes to 'ab' total and 'ab*'
        Author.objects.create(last_name='Ab ')    # Contributes to 'ab*'
        Author.objects.create(last_name='Ab1')    # Contributes to 'ab*'
        Author.objects.create(last_name='Ab!')    # Contributes to 'ab*'
        
        # We need more than min_quantity for 'a' and 'ab' to see 'ab*'
        extra_authors = [Author(last_name=f'Abc{i}') for i in range(10)]
        Author.objects.bulk_create(extra_authors)
        
        root = get_alphabet_tree(max_tree_depth=3, min_quantity=5, min_first_level_quantity=1)
        
        a_node = next(e for e in root.entries if e.name == 'a')
        ab_node = next(e for e in a_node.entries if e.name == 'ab')
        
        names = [e.name for e in ab_node.entries]
        self.assertIn('abc', names)
        self.assertIn('ab*', names)

    @parameterized.expand([
        (1, ['a']),
        (2, ['a', 'aa']),
        (3, ['a', 'aa', 'aaa']),
        (4, ['a', 'aa', 'aaa', 'aaaa']),
        (0, ['a']),   # Should default to 1
        (-1, ['a']),  # Should default to 1
    ])
    def test_different_tree_depths(self, max_depth, expected_path):
        """
        Test that the tree expands exactly up to max_tree_depth for various values.
        """
        authors = [Author(last_name=f'Aaaaaa{i}') for i in range(10)]
        Author.objects.bulk_create(authors)

        root = get_alphabet_tree(max_tree_depth=max_depth, min_quantity=2, min_first_level_quantity=1)

        current_node = root
        for node_name in expected_path:
            node_names = [e.name for e in current_node.entries]
            self.assertIn(node_name, node_names, f"Node '{node_name}' not found in {node_names} for max_depth={max_depth}")
            current_node = next(e for e in current_node.entries if e.name == node_name)

        self.assertEqual(len(current_node.entries), 0, f"Node '{current_node.name}' should have no children for max_depth={max_depth}")
