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
        self.assertEqual(root.authors_quantity, 0)

    def test_basic_categorization(self):
        """
        Test that authors are correctly categorized into alpha, digit, and other.
        """
        Author.objects.create(last_name='Abbott')
        Author.objects.create(last_name='123')
        Author.objects.create(last_name='!@#')
        
        root = get_alphabet_tree()
        names = [e.name for e in root.entries]
        
        self.assertIn('a', names)
        self.assertIn('0-9', names)
        self.assertIn('Other symbols', names)
        
        a_node = next(e for e in root.entries if e.name == 'a')
        self.assertEqual(a_node.authors_quantity, 1)
        
        digit_node = next(e for e in root.entries if e.name == '0-9')
        self.assertEqual(digit_node.authors_quantity, 1)
        
        other_node = next(e for e in root.entries if e.name == 'Other symbols')
        self.assertEqual(other_node.authors_quantity, 1)

    def test_case_insensitivity(self):
        """
        Test that the grouping is case-insensitive.
        """
        Author.objects.create(last_name='Abbott')
        Author.objects.create(last_name='abbott')
        
        root = get_alphabet_tree()
        self.assertEqual(len(root.entries), 1)
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
        
        root = get_alphabet_tree(min_quantity=min_quantity)
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
        # Trigger expansion for 'a', then 'aa', then 'aaa'
        # Level 1: 'a' > 2
        # Level 2: 'aa' > 2
        # Level 3: 'aaa' > 2
        authors = [
            Author(last_name='Aaa1'),
            Author(last_name='Aaa2'),
            Author(last_name='Aaa3'),
        ]
        Author.objects.bulk_create(authors)
        
        root = get_alphabet_tree(max_tree_depth=3, min_quantity=2)
        
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
        
        # min_quantity=5 should trigger expansion of 'a' and 'ab'
        root = get_alphabet_tree(min_quantity=5)
        
        a_node = next(e for e in root.entries if e.name == 'a')
        ab_node = next(e for e in a_node.entries if e.name == 'ab')
        
        # ab_node entries should include 'abc' and 'ab*'
        names = [e.name for e in ab_node.entries]
        self.assertIn('abc', names)
        self.assertIn('ab*', names)
        
        ab_star_node = next(e for e in ab_node.entries if e.name == 'ab*')
        self.assertEqual(ab_star_node.authors_quantity, 4) # 'Ab', 'Ab ', 'Ab1', 'Ab!'

    def test_max_tree_depth_limit(self):
        """
        Test that the tree does not expand beyond max_tree_depth.
        """
        # Level 1: 'a'
        # Level 2: 'aa'
        # Level 3: 'aaa'
        # Level 4: 'aaaa' (should NOT be created if max_tree_depth=3)
        authors = [Author(last_name=f'Aaaa{i}') for i in range(10)]
        Author.objects.bulk_create(authors)
        
        root = get_alphabet_tree(max_tree_depth=3, min_quantity=2)
        
        a_node = next(e for e in root.entries if e.name == 'a')
        aa_node = next(e for e in a_node.entries if e.name == 'aa')
        aaa_node = next(e for e in aa_node.entries if e.name == 'aaa')
        
        # aaa_node should have NO children because depth limit is reached
        self.assertEqual(len(aaa_node.entries), 0)
        self.assertEqual(aaa_node.authors_quantity, 10)
