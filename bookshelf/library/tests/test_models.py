from django.test import TestCase
from django.core.exceptions import ValidationError
from parameterized import parameterized_class

from library.models import BookSeries, Genre, Author


@parameterized_class(
    ('model',),
    [
        (BookSeries,),
        (Genre,),
        (Author,),
    ]
)
class RecursiveHierarchyTest(TestCase):
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

        self.assert_(True)


class AuthorHierarchyTest(TestCase):
    def test_wrong_parent(self):
        main_author = Author.objects.create(last_name='Main')
        main_author.full_clean()

        child_author_1 = Author.objects.create(last_name='Child 1', main_author=main_author)
        child_author_1.full_clean()

        with self.assertRaises(ValidationError):
            child_author_2 = Author(first_name='Child 2', main_author=child_author_1)
            child_author_2.full_clean()

