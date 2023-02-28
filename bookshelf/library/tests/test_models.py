from django.test import TestCase
from django.core.exceptions import ValidationError
from parameterized import parameterized_class

from library.models import BookSeries, Genre


@parameterized_class(
    ('model',),
    [
        (BookSeries,),
        (Genre,),
    ]
)
class RecursiveHierarchyTest(TestCase):
    def test_wrong_parent(self):
        instance = self.model(name='Test')
        instance.code = 1
        instance.save()

        with self.assertRaises(ValidationError):
            instance.parent = instance
            instance.full_clean()

    def test_proper_parent(self):
        parent_instance = self.model(name='Parent')
        parent_instance.code = 1
        parent_instance.full_clean()
        parent_instance.save()

        child_instance = self.model(name='Child', parent=parent_instance)
        child_instance.code = 2
        child_instance.full_clean()
        child_instance.save()

        self.assert_(True)
