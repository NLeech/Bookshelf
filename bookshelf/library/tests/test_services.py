from django.test import TestCase
from django.core.exceptions import ValidationError
from parameterized import parameterized_class

from library.models import BookSeries, Genre, Author
from third_part_libraries.models import FlibustaAuthor
from library.sevices import update_authors_from_flibusta


class AuthorUpdatingTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        author = Author.objects.create(last_name='Existing author')
        existing_flibusta_author = FlibustaAuthor.objects.create(last_name='Existing author', library_author=author)
        FlibustaAuthor.objects.create(last_name='New pseudonym 0', main_author=existing_flibusta_author)

        new_flibusta_author = FlibustaAuthor.objects.create(last_name='New flibusta author 1')
        FlibustaAuthor.objects.create(last_name='New pseudonym 1', main_author=new_flibusta_author)
        new_flibusta_author = FlibustaAuthor.objects.create(last_name='New flibusta author 2')
        FlibustaAuthor.objects.create(last_name='New pseudonym 2', main_author=new_flibusta_author)

    def test_updating_from_flibusta(self):
        self.assertEquals(Author.objects.count(), 1)
        update_authors_from_flibusta()

        self.assertEquals(Author.objects.count(), 6)
        self.assertEquals(Author.objects.filter(main_author=None).count(), 3)
        self.assertEquals(Author.objects.exclude(main_author=None).count(), 3)
        self.assertIsNotNone(Author.objects.filter(last_name='New pseudonym 0').first())
        self.assertIsNotNone(Author.objects.filter(last_name='New flibusta author 1').first())
        self.assertIsNotNone(Author.objects.filter(last_name='New pseudonym 2').first())

        update_authors_from_flibusta()
        self.assertEquals(Author.objects.count(), 6)


