from django.core.exceptions import ValidationError
from parameterized import parameterized_class, parameterized

from bookshelf.tests.base_test import BaseTestCase
from library.models import BookSeries, Genre, Author, Book, Language


@parameterized_class(
    ('model',),
    [
        (BookSeries,),
        (Genre,),
        (Author,),
    ]
)
class LoopHierarchyTest(BaseTestCase):
    def test_wrong_parent(self):
        instance = self.model()
        instance.name = 'Test'
        instance.last_name = 'Test'
        instance.code = 'test'
        instance.save()

        with self.assertRaises(ValidationError):
            instance.parent = instance
            instance.main_author = instance
            instance.full_clean()

    def test_proper_parent(self):
        parent_instance = self.model()

        parent_instance.name = 'Parent'
        parent_instance.last_name = 'Parent'
        parent_instance.code = 'test'

        parent_instance.full_clean()
        parent_instance.save()

        child_instance = self.model()

        child_instance.name = 'Child'
        child_instance.last_name = 'Child'
        child_instance.code = 'child'

        child_instance.parent = parent_instance
        child_instance.main_author = parent_instance

        child_instance.full_clean()
        child_instance.save()

        self.assertEqual(self.model.objects.count(), 2)


class AuthorHierarchyTest(BaseTestCase):
    def test_wrong_parent(self):
        main_author = Author.objects.create(last_name='Main')
        main_author.full_clean()

        child_author_1 = Author.objects.create(last_name='Child 1', main_author=main_author)
        child_author_1.full_clean()

        with self.assertRaises(ValidationError):
            child_author_2 = Author(first_name='Child 2', main_author=child_author_1)
            child_author_2.full_clean()


class BookModelTest(BaseTestCase):
    def test_book_str(self):
        language = Language.objects.create(code='en', name='English')
        book = Book.objects.create(title='Test Book', language=language)
        self.assertEqual(str(book), 'Test Book')

    def test_book_fields(self):
        """
        Verify that size and file_type fields are correctly saved and retrieved.
        """
        language = Language.objects.create(code='en', name='English')
        book = Book.objects.create(
            title='Test Book',
            language=language,
            size=1024,
            file_type='epub'
        )
        book.refresh_from_db()
        self.assertEqual(book.size, 1024)
        self.assertEqual(book.file_type, 'epub')

    @parameterized.expand([
        ('0_bytes', 0, '0 B'),
        ('512_bytes', 512, '512 B'),
        ('1_kb', 1024, '1.00 KB'),
        ('1_52_kb', 1560, '1.52 KB'),
        ('1_mb', 1048576, '1.00 MB'),
        ('1_78_mb', 1866465, '1.78 MB'),
    ])
    def test_book_size_str(self, name, size, expected):
        """
        Verify that size_str returns human-readable format correctly.
        """
        language = Language.objects.create(code='en', name='English')
        book = Book(title='Test Book', language=language, size=size)
        self.assertEqual(book.size_str, expected)

