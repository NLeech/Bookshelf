import logging
from dataclasses import dataclass, field
from sys import prefix

from django.db import transaction
from django.db.models import Count
from django.db.models.functions import Left, Lower

from third_party_libraries.models import FlibustaAuthor, FlibustaGenre
from library.models import Author, Genre


MAX_TREE_DEPTH = 3


@dataclass(order=True)
class AlphabetTree:
    """
    A tree structure for storing authors grouped by the first letters of their last names.
    """
    name: str = field(compare=True)
    regex: str = field(default='', compare=False, repr=False)
    authors_quantity: int = field(default=0, compare=False, repr=True)
    entries: list['AlphabetTree'] = field(default_factory=list, compare=False, repr=False)

    def __str__(self):
        return f'{self.name.capitalize()}'


def get_alphabet_tree() -> AlphabetTree:
    """
    Get a tree structure for storing authors grouped by the first letters of their last names.
    :return: the root of the tree
    """

    root = AlphabetTree(name='')

    # first level -
    # by the first letter of the last name
    results = (
        Author.objects
        .filter(last_name__regex=r'^[[:alpha:]]')
        .annotate(name = Left(Lower('last_name'), 1))
        .values('name')
        .annotate(authors_quantity=Count('id'))
        .order_by('name')
    )
    root.entries.extend(
        [
            AlphabetTree(name=result['name'], authors_quantity=result['authors_quantity']) for result in results
        ]
    )

    populate_branches(tree=root, level=2)

    # digits and other symbols are at the end of the list
    result = (
        Author.objects
        .filter(last_name__regex=r'^[0-9]')
        .count()
    )

    if result > 0:
        root.entries.append(AlphabetTree(
            name='0-9',
            regex=r'^[0-9]',
            authors_quantity=result,
        ))

    result = (
        Author.objects
        .filter(last_name__regex=r'^[^[:alpha:][:digit:]]')
        .count()
    )

    if result > 0:
        root.entries.append(AlphabetTree(
            name='Other symbols',
            regex=r'^[^[:alpha:][:digit:]]',
            authors_quantity=result,
        ))

    return root


def populate_branches(tree: AlphabetTree, level: int, min_quantity: int = 50) -> None:
    """
    Populate the branches of the tree with authors grouped by the first letters of their last names.
    :param tree: the tree to populate
    :param level: the level of the tree to populate (2 - by the first two letters, etc.)
    :param min_quantity: the minimum quantity of authors in a branch to populate it with sub-branches.
            If the quantity of authors in a branch is less than min_quantity,
            the branch will not be populated with sub-branches.
            This is done to avoid creating too many branches with a small number of authors in them.
    """
    for element in tree.entries:
        if element.authors_quantity > min_quantity:
            # only letters after the first letters
            results = (
                Author.objects
                .filter(last_name__iregex=r'^' + element.name + r'[[:alpha:]]')
                .annotate(name=Left(Lower('last_name'), level))
                .values('name')
                .annotate(authors_quantity=Count('id'))
                .order_by('name')
            )
            element.entries.extend(
                [
                    AlphabetTree(name=result['name'], authors_quantity=result['authors_quantity']) for result in results
                ]
            )

            if level < MAX_TREE_DEPTH:
                populate_branches(element, level + 1, min_quantity)

            # other symbols or nothing after the first letters
            # regex = r'^' + element.name + r'[^[:alpha:]]?'
            regex = r'^' + element.name + r'([^[:alpha:]].*)?$'
            result = (
                Author.objects
                .filter(last_name__iregex=regex)
                .count()
            )

            if result > 0:
                element.entries.append(AlphabetTree(
                    name=element.name + '*',
                    regex=regex,
                    authors_quantity=result,
                ))


def get_or_create_author(flibusta_author: FlibustaAuthor, main_author: Author = None) -> Author:
    """
    Create an Author from a FlibustaAuthor, link them together.
    If the Author with the same name already exists (with the same first, middle and last names and main_author),
    return the existing Author.
    If main_author is provided, the created author will be a pseudonym of main_author.
    Otherwise, the created author will be a main author.
    :param flibusta_author: flibusta author to create an Author from
    :param main_author: a main author for the created author (if any)
    :return: created or existing Author
    """
    author, created = Author.objects.get_or_create(
        first_name=flibusta_author.first_name,
        middle_name=flibusta_author.middle_name,
        last_name=flibusta_author.last_name,
        main_author=main_author,
        defaults={'nickname': flibusta_author.nickname,
                  'email': flibusta_author.email,
                  'homepage': flibusta_author.homepage}
    )

    flibusta_author.library_author = author
    flibusta_author.save()

    if created:
        logging.info(f'Created new author {author}')

    return author


def update_authors_from_flibusta() -> None:
    """
    Update the Author table from the FlibustaAuthor table.
    If an author from the FlibustaAuthor table does not exist in the Author table, create it.
    The update is done in two stages: first, all main authors are created, then all pseudonyms are created.
    This is done to ensure that all main authors exist before creating pseudonyms.
    After creating an Author, the corresponding FlibustaAuthor.library_author field is set to the created Author for the
    sake of future updates.
    This function should be called after updating the FlibustaAuthor table from Flibusta.
    """
    #  the first stage - update main authors
    new_flibusta_authors = FlibustaAuthor.objects.filter(library_author=None, main_author=None)
    with transaction.atomic():
        for flibusta_author in new_flibusta_authors:
            main_author = get_or_create_author(flibusta_author)

            # update pseudonyms
            new_flibusta_pseudonyms = flibusta_author.different_names.filter(library_author=None)
            for flibusta_pseudonym in new_flibusta_pseudonyms:
                get_or_create_author(flibusta_pseudonym, main_author)

    # update pseudonyms (after the first stage of updating, only pseudonyms remained in the FlibustaAuthor table)
    new_flibusta_pseudonyms = FlibustaAuthor.objects.filter(library_author=None).select_related('main_author')
    with transaction.atomic():
        for flibusta_pseudonym in new_flibusta_pseudonyms:
            get_or_create_author(flibusta_pseudonym, flibusta_pseudonym.main_author.library_author)


def update_genres_from_flibusta():
    """
    Update the Genre table from the FlibustaGenre table.
    If a genre from the FlibustaGenre table does not exist in the Genre table, create it.
    This function should be called after updating the FlibustaGenre table from Flibusta.
    """
    with transaction.atomic():
        for flibusta_genre in FlibustaGenre.objects.all():
            # metagenre first, then genre
            metagenre, created = Genre.objects.get_or_create(
                code=flibusta_genre.genre_meta,
                defaults={
                    'name': flibusta_genre.genre_meta,
                }
            )
            if created:
                logging.info(f'Created new genre {metagenre}')

            genre, created = Genre.objects.get_or_create(
                code=flibusta_genre.genre_code,
                defaults={
                    'name': flibusta_genre.genre_desc,
                    'parent': metagenre,
                }
            )
            if created:
                logging.info(f'Created new genre {genre}')


