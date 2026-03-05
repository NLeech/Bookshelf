import logging
from collections import defaultdict
from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import Count, Case, When, Value, CharField
from django.db.models.functions import Left, Lower

from third_party_libraries.models import FlibustaAuthor, FlibustaGenre
from library.models import Author, Genre


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


def recursive_defaultdict(depth: int) -> defaultdict:
    """
    Create a recursive defaultdict for storing the tree structure.
    :param depth: depth of the tree (number of levels)
    :return: defaultdict with the specified depth
    """

    if depth <= 1:
        return defaultdict(lambda: {
        'total': 0,
        'star': 0,
    })

    return defaultdict(lambda: {
        'total': 0,
        'star': 0,
        'sub': recursive_defaultdict(depth - 1)
    })


def add_prefix_level(prev_level: defaultdict, prefix: str, quantity: int, level: int, max_level) -> None:
    current_prefix = prefix[:level]
    prev_level['sub'][current_prefix]['total'] += quantity

    if len(prefix) > level and prefix[level].isalpha():
        if level < max_level:
            add_prefix_level(prev_level['sub'][current_prefix] , prefix, quantity, level + 1, max_level)
    else:
        prev_level['sub'][current_prefix]['star'] += quantity


def get_alphabet_tree(max_tree_depth: int = 3, min_quantity: int = 50) -> AlphabetTree:
    """
    Get a tree structure for storing authors grouped by the first letters of their last names.
    Tree example:
    - a
        - aa (authors with last names starting with 'aa')
            - aaa (authors with last names starting with 'aaa')
            - aab (authors with last names starting with 'aab')
            - aa* (only non-alpha after 'aa' or nothing after 'aa')
        - ab (authors with last names starting with 'ab')
        - a* (only non-alpha after 'a' or nothing after 'a')
    - b

    ...

    - 0-9 (authors with last names starting with a digit, witout further grouping)
    - Other symbols (authors with last names starting with a non-alphanumeric character, without further grouping)

    The tree is built in a way that if the number of authors in a branch is greater than min_quantity,
    the branch is expanded to the next level.
    The tree is built up to max_tree_depth levels. max_tree_depth should be at least 1, otherwise it will be set to 1.
    :return: the root of the tree
    """

    max_tree_depth = max(1, max_tree_depth)

    # Get all prefix counts up to max_tree_depth for each category
    counts = (
        Author.objects
        .annotate(
            category=Case(
                When(last_name__regex=r'^[[:alpha:]]', then=Value('alpha')),
                When(last_name__regex=r'^[0-9]', then=Value('digit')),
                default=Value('other'),
                output_field=CharField(),
            ),
            prefix=Left(Lower('last_name'), max_tree_depth)
        )
        .values('category', 'prefix')
        .annotate(authors_quantity=Count('id'))
    )

    # Intermediate storage for aggregation
    level1_data = recursive_defaultdict(max_tree_depth)

    digit_count = 0
    other_count = 0

    for item in counts:
        category = item['category']
        prefix = item['prefix']
        quantity = item['authors_quantity']

        # empty last name
        if not prefix:
            other_count += quantity
            continue

        if category == 'alpha':
            p1 = prefix[0]
            level1_data[p1]['total'] += quantity

            if len(prefix) > 1 and prefix[1].isalpha():
                add_prefix_level(level1_data[p1], prefix, quantity, 2, max_tree_depth)
            else:
                level1_data[p1]['star'] += quantity
        elif category == 'digit':
            digit_count += quantity
        else:
            other_count += quantity

    root = AlphabetTree(name='')

    # Build the tree from aggregated data
    for p1 in sorted(level1_data.keys()):
        data1 = level1_data[p1]
        node1 = AlphabetTree(name=p1, authors_quantity=data1['total'])
        root.entries.append(node1)

        if node1.authors_quantity > min_quantity:
            # Expand to level 2
            for p2 in sorted(data1['sub'].keys()):
                data2 = data1['sub'][p2]
                node2 = AlphabetTree(name=p2, authors_quantity=data2['total'])
                node1.entries.append(node2)

                if node2.authors_quantity > min_quantity:
                    # Expand to level 3
                    for p3 in sorted(data2['sub'].keys()):
                        node3 = AlphabetTree(name=p3, authors_quantity=data2['sub'][p3]['total'])
                        node2.entries.append(node3)

                    if data2['star'] > 0:
                        node2.entries.append(AlphabetTree(
                            name=p2 + '*',
                            regex=fr'^{p2}([^[:alpha:]].*)?$',
                            authors_quantity=data2['star']
                        ))

            if data1['star'] > 0:
                node1.entries.append(AlphabetTree(
                    name=p1 + '*',
                    regex=fr'^{p1}([^[:alpha:]].*)?$',
                    authors_quantity=data1['star']
                ))

    if digit_count > 0:
        root.entries.append(AlphabetTree(
            name='0-9',
            regex=r'^[0-9]',
            authors_quantity=digit_count,
        ))

    if other_count > 0:
        root.entries.append(AlphabetTree(
            name='Other symbols',
            regex=r'^[^[:alpha:][:digit:]]',
            authors_quantity=other_count,
        ))

    return root


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


