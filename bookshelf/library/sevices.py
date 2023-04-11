import logging
from django.db import transaction

from third_part_libraries.models import FlibustaAuthor
from library.models import Author


def create_author(flibusta_author: FlibustaAuthor, main_author: Author = None) -> Author:
    """
    Create author from flibusta author if it not exists.
    Link flibusta author with created author
    :param flibusta_author: flibusta author
    :param main_author: main author
    :return: created or found author

    """
    author, created = Author.objects.get_or_create(
        first_name=flibusta_author.first_name,
        middle_name=flibusta_author.middle_name,
        last_name=flibusta_author.last_name,
        main_author=main_author,
    )

    flibusta_author.library_author = author
    flibusta_author.save()

    if created:
        logging.info(f'Created new author {author}')

    return author


def update_authors_from_flibusta() -> None:

    #  the first stage - update main authors
    new_flibusta_authors = FlibustaAuthor.objects.filter(library_author=None, main_author=None)
    with transaction.atomic():
        for flibusta_author in new_flibusta_authors:
            main_author = create_author(flibusta_author)

            # update pseudonyms
            new_flibusta_pseudonyms = flibusta_author.different_names.filter(library_author=None)
            for flibusta_pseudonym in new_flibusta_pseudonyms:
                create_author(flibusta_pseudonym, main_author)

    # update pseudonyms
    new_flibusta_pseudonyms = FlibustaAuthor.objects.filter(library_author=None).select_related('main_author')
    with transaction.atomic():
        for flibusta_pseudonym in new_flibusta_pseudonyms:
            create_author(flibusta_pseudonym, flibusta_pseudonym.main_author.library_author)





