from django.test import TestCase

from library.models import BookSeries, Genre, Author
from third_party_libraries.models import FlibustaAuthor, FlibustaGenre
from library.sevices import update_authors_from_flibusta, update_genres_from_flibusta


class AuthorUpdatingTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Existing author that should NOT be updated with new info
        author = Author.objects.create(
            last_name='Existing author',
            nickname='old_nick',
            email='old@email.com',
            homepage='old.home'
        )
        existing_flibusta_author = FlibustaAuthor.objects.create(
            last_name='Existing author',
            library_author=author,
            nickname='new_nick_ignored',
            email='new_ignored@email.com',
            homepage='new.ignored.home'
        )
        FlibustaAuthor.objects.create(
            last_name='New pseudonym 0',
            main_author=existing_flibusta_author,
            nickname='nick0',
            email='p0@email.com',
            homepage='p0.home'
        )

        # New author that should be created with all fields
        new_flibusta_author_1 = FlibustaAuthor.objects.create(
            last_name='New flibusta author 1',
            nickname='nick1',
            email='a1@email.com',
            homepage='a1.home'
        )
        FlibustaAuthor.objects.create(
            last_name='New pseudonym 1',
            main_author=new_flibusta_author_1,
            nickname='nickp1',
            email='p1@email.com',
            homepage='p1.home'
        )

        # Another new author without extra fields
        new_flibusta_author_2 = FlibustaAuthor.objects.create(last_name='New flibusta author 2')
        FlibustaAuthor.objects.create(last_name='New pseudonym 2', main_author=new_flibusta_author_2)

    def test_updating_from_flibusta(self):
        self.assertEqual(Author.objects.count(), 1)
        update_authors_from_flibusta()

        self.assertEqual(Author.objects.count(), 6)
        self.assertEqual(Author.objects.filter(main_author=None).count(), 3)
        self.assertEqual(Author.objects.exclude(main_author=None).count(), 3)
        self.assertIsNotNone(Author.objects.filter(last_name='New pseudonym 0').first())
        self.assertIsNotNone(Author.objects.filter(last_name='New flibusta author 1').first())
        self.assertIsNotNone(Author.objects.filter(last_name='New pseudonym 2').first())

        # Check that the existing author was NOT updated
        existing_author = Author.objects.get(last_name='Existing author')
        self.assertEqual(existing_author.nickname, 'old_nick')
        self.assertEqual(existing_author.email, 'old@email.com')
        self.assertEqual(existing_author.homepage, 'old.home')

        # Check new pseudonym for existing author
        pseudonym0 = Author.objects.get(last_name='New pseudonym 0')
        self.assertEqual(pseudonym0.nickname, 'nick0')
        self.assertEqual(pseudonym0.email, 'p0@email.com')
        self.assertEqual(pseudonym0.homepage, 'p0.home')

        # Check new author with all fields
        author1 = Author.objects.get(last_name='New flibusta author 1')
        self.assertEqual(author1.nickname, 'nick1')
        self.assertEqual(author1.email, 'a1@email.com')
        self.assertEqual(author1.homepage, 'a1.home')

        # Check pseudonym for new author
        pseudonym1 = Author.objects.get(last_name='New pseudonym 1')
        self.assertEqual(pseudonym1.nickname, 'nickp1')
        self.assertEqual(pseudonym1.email, 'p1@email.com')
        self.assertEqual(pseudonym1.homepage, 'p1.home')

        # Check new author without extra fields (should have defaults)
        author2 = Author.objects.get(last_name='New flibusta author 2')
        self.assertEqual(author2.nickname, '')
        self.assertEqual(author2.email, '')
        self.assertEqual(author2.homepage, '')

        update_authors_from_flibusta()
        self.assertEqual(Author.objects.count(), 6)


class UpdateGenresFromFlibustaTest(TestCase):
    def test_update_genres_from_flibusta_empty(self):
        self.assertEqual(Genre.objects.count(), 0)
        update_genres_from_flibusta()
        self.assertEqual(Genre.objects.count(), 0)

    def test_update_genres_from_flibusta_creates_new_genres(self):
        FlibustaGenre.objects.create(genre_code='sf', genre_desc='Science Fiction', genre_meta='science_fiction')
        FlibustaGenre.objects.create(genre_code='fantasy', genre_desc='Fantasy', genre_meta='fantasy')

        self.assertEqual(Genre.objects.count(), 0)
        update_genres_from_flibusta()
        self.assertEqual(Genre.objects.count(), 3)

        sf_meta = Genre.objects.get(code='science_fiction')
        self.assertEqual(sf_meta.name, 'science_fiction')
        self.assertIsNone(sf_meta.parent)

        sf = Genre.objects.get(code='sf')
        self.assertEqual(sf.name, 'Science Fiction')
        self.assertEqual(sf.parent, sf_meta)

        fantasy_meta = Genre.objects.get(code='fantasy')
        self.assertEqual(fantasy_meta.name, 'fantasy')
        self.assertIsNone(fantasy_meta.parent)

    def test_update_genres_from_flibusta_does_not_create_existing_genres(self):
        FlibustaGenre.objects.create(genre_code='sf', genre_desc='Science Fiction', genre_meta='science_fiction')
        update_genres_from_flibusta()
        self.assertEqual(Genre.objects.count(), 2)

        update_genres_from_flibusta()
        self.assertEqual(Genre.objects.count(), 2)

    def test_update_genres_from_flibusta_mixed_genres(self):
        FlibustaGenre.objects.create(genre_code='sf', genre_desc='Science Fiction', genre_meta='science_fiction')
        update_genres_from_flibusta()
        self.assertEqual(Genre.objects.count(), 2)

        FlibustaGenre.objects.create(genre_code='fantasy', genre_desc='Fantasy', genre_meta='fantasy')
        update_genres_from_flibusta()
        self.assertEqual(Genre.objects.count(), 3)