from django.test import TestCase, override_settings
from library.models import Author, Book, Language
from library.services import get_alphabet_tree, find_alphabet_node, AlphabetTree
from parameterized import parameterized

@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class GetAlphabetTreeTest(TestCase):
    """
    Tests for the get_alphabet_tree function.
    """

    def test_empty_database(self):
        """
        Test that an empty database returns a root with no entries.
        """
        root = get_alphabet_tree(Author.objects.all(), 'last_name')
        self.assertEqual(len(root.entries), 0)

    def test_basic_categorization(self):
        """
        Test that authors are correctly categorized into alpha, digit, and other.
        Use min_first_level_quantity=1 to keep alpha nodes at root.
        """
        Author.objects.create(last_name='Abbott')
        Author.objects.create(last_name='123')
        Author.objects.create(last_name='!@#')
        
        root = get_alphabet_tree(Author.objects.all(), 'last_name', min_first_level_quantity=1)
        names = [e.name for e in root.entries]
        
        self.assertIn('a', names)
        self.assertIn('0-9', names)
        self.assertIn('other', names)
        
        a_node = next(e for e in root.entries if e.name == 'a')
        self.assertEqual(a_node.quantity, 1)
        self.assertEqual(str(a_node), 'A')
        
        digit_node = next(e for e in root.entries if e.name == '0-9')
        self.assertEqual(digit_node.quantity, 1)
        
        other_node = next(e for e in root.entries if e.name == 'other')
        self.assertEqual(len(other_node.entries), 1)
        self.assertEqual(other_node.entries[0].name, '* (all non-alpha)')

    def test_low_quantity_alpha_moved_to_other(self):
        """
        Test that alpha nodes with quantity < min_first_level_quantity are moved to 'other'.
        Check that high-quantity nodes stay at root and other_node regex is properly constructed.
        """
        # Create high-quantity prefix 'b' (3 authors)
        Author.objects.create(last_name='Baker')
        Author.objects.create(last_name='Brown')
        Author.objects.create(last_name='Bell')

        # Create low-quantity prefixes 'a' and 'z' (1 author each)
        Author.objects.create(last_name='Abbott')
        Author.objects.create(last_name='Zebra')

        # Create non-alpha
        Author.objects.create(last_name='!@#')

        # min_first_level_quantity=2: 'b' should stay at root, 'a' and 'z' should move to 'other'
        root = get_alphabet_tree(Author.objects.all(), 'last_name', min_first_level_quantity=2)

        root_names = [e.name for e in root.entries]
        self.assertIn('b', root_names)
        self.assertIn('other', root_names)
        self.assertNotIn('a', root_names)
        self.assertNotIn('z', root_names)

        other_node = next(e for e in root.entries if e.name == 'other')
        child_names = [e.name for e in other_node.entries]
        self.assertIn('a', child_names)
        self.assertIn('z', child_names)
        self.assertIn('* (all non-alpha)', child_names)

        # Check regex: should include non-alpha pattern AND the moved prefixes
        self.assertEqual(other_node.regex, '^([^[:alpha:][:digit:]]|a|z)')

    def test_digits_always_at_root(self):
        """
        Test that '0-9' node stays at root even with low quantity.
        """
        Author.objects.create(last_name='123')
        
        root = get_alphabet_tree(Author.objects.all(), 'last_name', min_first_level_quantity=10)
        names = [e.name for e in root.entries]
        self.assertIn('0-9', names)

    def test_case_insensitivity(self):
        """
        Test that the grouping is case-insensitive.
        """
        Author.objects.create(last_name='Abbott')
        Author.objects.create(last_name='abbott')
        
        root = get_alphabet_tree(Author.objects.all(), 'last_name', min_first_level_quantity=1)
        self.assertEqual(root.entries[0].name, 'a')
        self.assertEqual(root.entries[0].quantity, 2)

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
        
        root = get_alphabet_tree(Author.objects.all(), 'last_name', min_quantity=min_quantity, min_first_level_quantity=1)
        a_node = next(e for e in root.entries if e.name == 'a')
        
        if should_expand:
            self.assertGreater(len(a_node.entries), 0)
            aa_node = next(e for e in a_node.entries if e.name == 'aa')
            self.assertEqual(aa_node.quantity, total_authors)
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
        
        root = get_alphabet_tree(Author.objects.all(), 'last_name', max_tree_depth=3, min_quantity=2, min_first_level_quantity=1)
        
        a_node = next(e for e in root.entries if e.name == 'a')
        self.assertGreater(len(a_node.entries), 0)
        
        aa_node = next(e for e in a_node.entries if e.name == 'aa')
        self.assertGreater(len(aa_node.entries), 0)
        
        aaa_node = next(e for e in aa_node.entries if e.name == 'aaa')
        self.assertEqual(aaa_node.quantity, 3)

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
        
        root = get_alphabet_tree(Author.objects.all(), 'last_name', max_tree_depth=3, min_quantity=5, min_first_level_quantity=1)
        
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

        root = get_alphabet_tree(Author.objects.all(), 'last_name', max_tree_depth=max_depth, min_quantity=2, min_first_level_quantity=1)

        current_node = root
        for node_name in expected_path:
            node_names = [e.name for e in current_node.entries]
            self.assertIn(node_name, node_names, f"Node '{node_name}' not found in {node_names} for max_depth={max_depth}")
            current_node = next(e for e in current_node.entries if e.name == node_name)

        self.assertEqual(len(current_node.entries), 0, f"Node '{current_node.name}' should have no children for max_depth={max_depth}")

    def test_empty_last_name(self):
        """
        Test that authors with empty last names are correctly categorized into 'other'.
        """
        Author.objects.create(last_name='')
        
        root = get_alphabet_tree(Author.objects.all(), 'last_name')
        other_node = next(e for e in root.entries if e.name == 'other')
        star_node = next(e for e in other_node.entries if e.name == '* (all non-alpha)')
        self.assertEqual(star_node.quantity, 1)

    def test_generic_alphabet_tree_books(self):
        """
        Verify that get_alphabet_tree works correctly for Book.objects.all() and 'title'.
        """
        lang = Language.objects.create(name='English', code='en')
        Book.objects.create(title='A Tale of Two Cities', language=lang)
        Book.objects.create(title='Brave New World', language=lang)
        Book.objects.create(title='1984', language=lang)
        
        root = get_alphabet_tree(Book.objects.all(), 'title', min_first_level_quantity=1)
        names = [e.name for e in root.entries]
        
        self.assertIn('a', names)
        self.assertIn('b', names)
        self.assertIn('0-9', names)
        
        a_node = next(e for e in root.entries if e.name == 'a')
        self.assertEqual(a_node.quantity, 1)

    def test_alphabet_tree_with_filtered_queryset(self):
        """
        Verify that get_alphabet_tree correctly calculates counts when provided with a queryset 
        already filtered by language or genre.
        """
        lang_en = Language.objects.create(name='English', code='en')
        lang_fr = Language.objects.create(name='French', code='fr')
        
        b1 = Book.objects.create(title='Apple', language=lang_en)
        b2 = Book.objects.create(title='Apricot', language=lang_fr)
        
        # Filtered by English: only 'Apple' should be counted
        qs = Book.objects.filter(language=lang_en)
        root = get_alphabet_tree(qs, 'title', min_first_level_quantity=1)
        
        a_node = next(e for e in root.entries if e.name == 'a')
        self.assertEqual(a_node.quantity, 1)


class FindAlphabetNodeTest(TestCase):
    """
    Tests for the find_alphabet_node function.
    """

    @classmethod
    def setUpTestData(cls):
        """Set up a simple alphabet tree for testing."""
        cls.root = AlphabetTree(name='')
        
        # Level 1
        cls.node_a = AlphabetTree(name='a', filter='a')
        cls.node_b = AlphabetTree(name='b', filter='b')
        cls.node_other = AlphabetTree(name='other', regex='^[^[:alpha:][:digit:]]')
        
        cls.root.entries = [cls.node_a, cls.node_b, cls.node_other]
        
        # Level 2 under 'a'
        cls.node_aa = AlphabetTree(name='aa', filter='aa')
        cls.node_ab = AlphabetTree(name='ab', filter='ab')
        cls.node_a_star = AlphabetTree(name='a*', regex='^a([^[:alpha:]].*)?$')
        
        cls.node_a.entries = [cls.node_aa, cls.node_ab, cls.node_a_star]

    @parameterized.expand([
        ("find_b", "b", "", "node_b"),
        ("find_aa", "aa", "", "node_aa"),
        ("find_aa_caps", "AA", "", "node_aa"),
        ("find_other_regex", "", "^[^[:alpha:][:digit:]]", "node_other"),
        ("find_a_star_regex", "", "^a([^[:alpha:]].*)?$", "node_a_star"),
        ("not_found", "nonexistent", "", None),
        ("empty_search", "", "", None),
    ])
    def test_find_alphabet_node(self, name, filter_val, regex_val, expected_node_attr):
        """Verifies find_alphabet_node behavior for various inputs."""
        expected_node = getattr(self, expected_node_attr) if expected_node_attr else None
        result = find_alphabet_node(self.root, filter_val, regex_val)
        self.assertEqual(result, expected_node)
