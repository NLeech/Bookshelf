from django.urls import reverse
from django.core.files.base import ContentFile
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from parameterized import parameterized

from bookshelf.tests.base_test import BaseTestCase
from library.models import Author, Language, Book
from library.tests.epub_test_utils import create_epub_nested_chapters
from library.tests.fb2_test_utils import create_fb2_nested_chapters

User = get_user_model()


class BookDetailViewTests(BaseTestCase):
    """
    Tests for the BookDetailView in library.views.
    """

    @classmethod
    def setUpTestData(cls):
        cls.author = Author.objects.create(first_name='John', last_name='Doe')
        cls.lang_en = Language.objects.create(code='en', name='English')
        
        # EPUB Book with nested chapters
        cls.epub_book = Book.objects.create(title='Test EPUB', language=cls.lang_en)
        cls.epub_book.authors.add(cls.author)
        with create_epub_nested_chapters() as f:
            cls.epub_book.file.save('test.epub', ContentFile(f.read()))
        
        # FB2 Book with nested chapters
        cls.fb2_book = Book.objects.create(title='Test FB2', language=cls.lang_en)
        cls.fb2_book.authors.add(cls.author)
        with create_fb2_nested_chapters() as f:
            cls.fb2_book.file.save('test.fb2', ContentFile(f.read()))
        
        # Book with no file
        cls.no_file_book = Book.objects.create(title='No File', language=cls.lang_en)

        # User for authentication
        cls.user = User.objects.create_user(username='testuser', email='test@example.com', password='password')
        # Assign permission to see full content and avoid redirects from PermissionRequiredMixin if it was used
        # Note: BookDetailView only uses LoginRequiredMixin, but it's good practice
        group = Group.objects.get(name='Book access')
        cls.user.groups.add(group)

    def setUp(self):
        self.client.login(username='testuser', password='password')

    def tearDown(self):
        # Ensure files are closed
        for book in Book.objects.all():
            if book.file:
                book.file.close()

    @parameterized.expand([
        ('epub', 'epub_book'),
        ('fb2', 'fb2_book'),
    ])
    def test_book_detail_view_status_code(self, name, book_attr):
        """
        Verify the view returns 200 OK and uses the correct template for both formats.
        """
        book = getattr(self, book_attr)
        response = self.client.get(reverse('library:book', args=[book.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'library/book.html')

    def test_book_detail_view_404(self):
        """
        Verify the view returns 404 for a non-existent book.
        """
        response = self.client.get(reverse('library:book', args=[999]))
        self.assertEqual(response.status_code, 404)

    @parameterized.expand([
        ('epub', 'epub_book'),
        ('fb2', 'fb2_book'),
    ])
    def test_book_detail_view_content(self, name, book_attr):
        """
        Verify hierarchical TOC structure and chapter content in context and response.
        """
        book = getattr(self, book_attr)
        response = self.client.get(reverse('library:book', args=[book.id]))
        self.assertEqual(response.status_code, 200)
        
        # Check context
        self.assertIn('chapters', response.context)
        self.assertIn('current_chapter', response.context)
        
        chapters = response.context['chapters']
        current_chapter = response.context['current_chapter']
        
        # The utils create 3 top-level chapters. 
        # Chapter 1 has 2 subchapters.
        # Chapter 3 has 1 subchapter.
        self.assertEqual(len(chapters), 3)
        self.assertEqual(chapters[0].title, 'Chapter 1')
        self.assertEqual(len(chapters[0].subchapters), 2)
        self.assertEqual(chapters[0].subchapters[0].title, 'Subchapter 1.1')
        
        # Verify initial chapter (index 0)
        self.assertEqual(current_chapter.title, 'Chapter 1')
        self.assertIn('Content of chapter 1.', current_chapter.content)
        
        # Check response body
        self.assertContains(response, 'Chapter 1')
        self.assertContains(response, 'Content of chapter 1.')
        self.assertContains(response, 'Subchapter 1.1') # Should be in TOC

    @parameterized.expand([
        ('epub', 'epub_book', 1, 'Subchapter 1.1'),
        ('epub', 'epub_book', 3, 'Chapter 2'),
        ('fb2', 'fb2_book', 1, 'Subchapter 1.1'),
        ('fb2', 'fb2_book', 3, 'Chapter 2'),
    ])
    def test_book_detail_view_chapter_selection(self, name, book_attr, index, expected_title):
        """
        Verify that selecting a chapter by index works correctly.
        Flattened indices for the nested structure:
        0: Chapter 1
        1: Subchapter 1.1
        2: Subchapter 1.2
        3: Chapter 2
        4: Chapter 3
        5: Subchapter 3.1
        """
        book = getattr(self, book_attr)
        response = self.client.get(reverse('library:book_chapter', args=[book.id, index]))
        self.assertEqual(response.status_code, 200)
        
        current_chapter = response.context['current_chapter']
        self.assertEqual(current_chapter.title, expected_title)
        self.assertContains(response, expected_title)

    @parameterized.expand([
        ('epub', 'epub_book'),
        ('fb2', 'fb2_book'),
    ])
    def test_book_detail_view_htmx_partial(self, name, book_attr):
        """
        Verify HTMX partial rendering.
        """
        book = getattr(self, book_attr)
        response = self.client.get(reverse('library:book', args=[book.id]), HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 200)
        self.assertIn('library/book.html#book_content', response.template_name)

    def test_book_detail_view_no_extractor(self):
        """
        Verify behavior when book has no file.
        """
        response = self.client.get(reverse('library:book', args=[self.no_file_book.id]))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context.get('chapters'))
        self.assertIsNone(response.context.get('current_chapter'))
        self.assertContains(response, 'No TOC available')

    def test_book_detail_view_invalid_chapter_index(self):
        """
        Verify that an invalid chapter index defaults to the first chapter.
        """
        # Index 99 is invalid, structure has 6 chapters total
        response = self.client.get(reverse('library:book_chapter', args=[self.epub_book.id, 99]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['current_chapter'].title, 'Chapter 1')

    @parameterized.expand([
        ('epub', 'epub_book'),
        ('fb2', 'fb2_book'),
    ])
    def test_book_detail_navigation_context(self, name, book_attr):
        """
        Verify that prev_chapter and next_chapter are correctly added to the context.
        Using index 1 (Subchapter 1.1).
        Structure: 0: Ch 1, 1: Sub 1.1, 2: Sub 1.2
        """
        book = getattr(self, book_attr)
        response = self.client.get(reverse('library:book_chapter', args=[book.id, 1]))
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context['prev_chapter'].title, 'Chapter 1')
        self.assertEqual(response.context['next_chapter'].title, 'Subchapter 1.2')

    @parameterized.expand([
        ('epub', 'epub_book'),
        ('fb2', 'fb2_book'),
    ])
    def test_book_detail_first_chapter_navigation(self, name, book_attr):
        """
        Verify navigation context for the first chapter (index 0).
        """
        book = getattr(self, book_attr)
        response = self.client.get(reverse('library:book_chapter', args=[book.id, 0]))
        self.assertEqual(response.status_code, 200)

        self.assertNotIn('prev_chapter', response.context)
        self.assertEqual(response.context['next_chapter'].title, 'Subchapter 1.1')

    @parameterized.expand([
        ('epub', 'epub_book'),
        ('fb2', 'fb2_book'),
    ])
    def test_book_detail_last_chapter_navigation(self, name, book_attr):
        """
        Verify navigation context for the last chapter (index 5).
        Structure: ... 4: Chapter 3, 5: Subchapter 3.1
        """
        book = getattr(self, book_attr)
        response = self.client.get(reverse('library:book_chapter', args=[book.id, 5]))
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context['prev_chapter'].title, 'Chapter 3')
        self.assertNotIn('next_chapter', response.context)

    @parameterized.expand([
        ('epub', 'epub_book'),
        ('fb2', 'fb2_book'),
    ])
    def test_book_detail_navigation_rendering(self, name, book_attr):
        """
        Verify that navigation links are rendered correctly in the HTML.
        """
        book = getattr(self, book_attr)
        # Request index 1 (Subchapter 1.1)
        response = self.client.get(reverse('library:book_chapter', args=[book.id, 1]))
        self.assertEqual(response.status_code, 200)

        # Check for two navigation blocks
        self.assertContains(response, '<nav class="d-flex justify-content-between my-3">', count=2)

        # Check for links with hx-get
        # Prev: Chapter 1 (index 0)
        prev_url = reverse('library:book_chapter', args=[book.id, 0])
        self.assertContains(response, f'hx-get="{prev_url}"')
        self.assertContains(response, 'Chapter 1')

        # Next: Subchapter 1.2 (index 2)
        next_url = reverse('library:book_chapter', args=[book.id, 2])
        self.assertContains(response, f'hx-get="{next_url}"')
        self.assertContains(response, 'Subchapter 1.2')
