import logging
import io
import mimetypes
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyzipper
from django.conf import settings
from django.db import transaction
from django.db.models import Count, Case, When, Value, CharField, Q, QuerySet
from django.db.models.functions import Left, Lower
from django.utils.text import get_valid_filename

from .models import Author, Genre, Language, Book
from .book_utils.book_file import BookFile
from .book_utils.epub_book_file import EpubBookFile
from .book_utils.fb2_book_file import Fb2BookFile


@dataclass(order=True)
class AlphabetTree:
    """
    A tree structure for storing authors grouped by the first letters of their last names.
    """
    name: str = field(compare=True)
    filter: str = field(default='', compare=False, repr=True)
    regex: str = field(default='', compare=False, repr=False)
    authors_quantity: int = field(default=0, compare=False, repr=True)
    entries: list['AlphabetTree'] = field(default_factory=list, compare=False, repr=False)

    def __str__(self) -> str:
        return f'{self.name.capitalize()}'


def _recursive_defaultdict(depth: int) -> defaultdict[str, Any]:
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
        'sub': _recursive_defaultdict(depth - 1)
    })


def _add_prefix_level(prev_level: defaultdict[str, Any], prefix: str, quantity: int, level: int, max_level: int) -> None:
    """
    Recursively make the tree structure for a given prefix and quantity.
    :param prev_level:  the level of the tree to which the prefix should be added
    :param prefix:  full prefix of the last name (up to max_level characters) for which the quantity is calculated
    :param quantity: quantity of authors with the given prefix
    :param level: level of the tree to which the prefix should be added (starting from 2)
    :param max_level:
    :return:
    """
    current_prefix = prefix[:level]
    prev_level['sub'][current_prefix]['total'] += quantity

    if len(prefix) > level and prefix[level].isalpha():
        if level < max_level:
            _add_prefix_level(prev_level['sub'][current_prefix], prefix, quantity, level + 1, max_level)
    else:
        prev_level['sub'][current_prefix]['star'] += quantity


def _build_tree_node(parent: AlphabetTree, prefix: str, data: dict[str, Any], min_quantity: int) -> None:
    """
    Recursively build the alphabet tree from aggregated prefix data.
    :param parent: the parent node to attach children to
    :param prefix: the current prefix string for this node
    :param data: dict with 'total', 'star', and optionally 'sub' keys
    :param min_quantity: threshold above which a node is expanded further
    """
    node = AlphabetTree(name=prefix, filter=prefix, authors_quantity=data['total'])
    parent.entries.append(node)

    if node.authors_quantity <= min_quantity or 'sub' not in data:
        return

    for sub_prefix in sorted(data['sub'].keys()):
        _build_tree_node(node, sub_prefix, data['sub'][sub_prefix], min_quantity)

    if data['star'] > 0:
        node.entries.append(AlphabetTree(
            name=prefix + '*',
            filter='',
            regex=fr'^{prefix}([^[:alpha:]].*)?$',
            authors_quantity=data['star']
        ))


def get_alphabet_tree(max_tree_depth: int = 3, min_quantity: int = 50, min_first_level_quantity: int = 10) -> AlphabetTree:
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

    - 0-9 (all digits last names)
    - other
        - * (all non-alpha last names)
        - ы (alpha prefixes with quantity < min_first_level_quantity)

    The tree is built in a way that if the number of authors in a branch is greater than min_quantity,
    the branch is expanded to the next level.
    The tree is built up to max_tree_depth levels. max_tree_depth should be at least 1, otherwise it will be set to 1.
    :param max_tree_depth: max depth of the tree
    :param min_quantity: threshold above which a node is expanded further
    :param min_first_level_quantity: threshold for first level nodes. If less, the node is moved to 'other'
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
    level1_data = _recursive_defaultdict(max_tree_depth)

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
                _add_prefix_level(level1_data[p1], prefix, quantity, 2, max_tree_depth)
            else:
                level1_data[p1]['star'] += quantity
        elif category == 'digit':
            digit_count += quantity
        else:
            other_count += quantity

    root = AlphabetTree(name='', filter='')

    # Build the tree from aggregated data
    other_node = AlphabetTree(name='other', filter='')

    # 1. Non-alpha authors go to other_node
    if other_count > 0:
        other_node.entries.append(AlphabetTree(
            name='* (all non-alpha last names)',
            filter='',
            regex=r'^[^[:alpha:][:digit:]]',
            authors_quantity=other_count,
        ))
        other_node.authors_quantity += other_count

    # Alpha nodes: high-quantity go to root, low-quantity go to other_node
    moved_prefixes = []
    for p1 in sorted(level1_data.keys()):
        if level1_data[p1]['total'] >= min_first_level_quantity:
            _build_tree_node(root, p1, level1_data[p1], min_quantity)
        else:
            _build_tree_node(other_node, p1, level1_data[p1], min_quantity)
            other_node.authors_quantity += level1_data[p1]['total']
            moved_prefixes.append(p1)

    if moved_prefixes:
        prefixes_pattern = '|'.join(moved_prefixes)
        other_node.regex = fr'^([^[:alpha:][:digit:]]|{prefixes_pattern})'
    else:
        other_node.regex = r'^[^[:alpha:][:digit:]]'


    if digit_count > 0:
        root.entries.append(AlphabetTree(
            name='0-9',
            filter='',
            regex=r'^[0-9]',
            authors_quantity=digit_count,
        ))

    if other_node.entries:
        root.entries.append(other_node)

    return root


def get_author_languages(author: Author) -> QuerySet[Language]:
    """
    Get all languages of the books written by the author.
    Each language is annotated with the count of books by this author in that language.
    """
    return (
        Language.objects
        .filter(books__authors=author)
        .annotate(book_count=Count('books', filter=Q(books__authors=author)))
        .order_by('name')
        .distinct()
    )


def get_author_genres_tree(author: Author) -> list[dict[str, Any]]:
    """
    Build a hierarchical tree of genres associated with the author's books.
    Includes ancestor genres even if they don't have books directly.
    The tree is sorted alphabetically at each level and includes the count of books for each genre.
    The tree is represented as a list of dicts with keys: 'genre' (Genre object), 'book_count' (int), and 'children' (list of dicts).
    """
    # Get all genres directly associated with the author's books, with book counts
    direct_genres_qs = (
        Genre.objects
        .filter(books__authors=author)
        .annotate(book_count=Count('books', filter=Q(books__authors=author)))
        .distinct()
    )

    if not direct_genres_qs.exists():
        return []

    # Fetch ALL genres once to avoid N+1 lookups for parents
    # Mapping id -> genre object
    all_genres = {g.id: g for g in Genre.objects.all()}
    
    # Map to store our tree data: {id: {"genre": genre_obj, "book_count": count, "children": []}}
    genre_map: dict[int, dict[str, Any]] = {}

    def add_genre_to_map(genre_id: int, count: int = 0) -> None:
        if genre_id not in all_genres:
            return

        if genre_id in genre_map:
            genre_map[genre_id]['book_count'] += count
            return

        genre_obj = all_genres[genre_id]
        genre_map[genre_id] = {
            'genre': genre_obj,
            'book_count': count,
            'children': []
        }

        if genre_obj.parent_id:
            add_genre_to_map(genre_obj.parent_id, 0)

    for g in direct_genres_qs:
        add_genre_to_map(g.id, getattr(g, 'book_count', 0))

    # Build the tree structure
    root_nodes: list[dict[str, Any]] = []
    for g_id in sorted(genre_map.keys()):
        data = genre_map[g_id]
        genre_obj = data['genre']
        if genre_obj.parent_id and genre_obj.parent_id in genre_map:
            genre_map[genre_obj.parent_id]['children'].append(data)
        else:
            root_nodes.append(data)

    # Sort children recursively
    def sort_tree(nodes: list[dict[str, Any]]) -> None:
        nodes.sort(key=lambda x: x['genre'].name.lower())
        for node in nodes:
            sort_tree(node['children'])

    sort_tree(root_nodes)
    return root_nodes


def get_book_extractor(book: Book) -> EpubBookFile | Fb2BookFile | None:
    """Load the appropriate book extractor based on the file extension.

    Handles password-protected ZIP files if necessary.

    Args:
        book: The Book model instance.

    Returns:
        An instance of EpubBookFile, Fb2BookFile, or None if unsupported.
    """
    if not book.file:
        return None

    file_path = Path(book.file.path)
    file_name = book.file.name.lower()

    if file_name.endswith('.zip'):
        try:
            with pyzipper.AESZipFile(file_path) as zf:
                zf.setpassword(settings.BOOK_PWD)
                namelist = zf.namelist()
                if not namelist:
                    return None
                
                # Assume the first file is the book content
                inner_filename = namelist[0]
                extension = inner_filename.split('.')[-1].lower()
                extractor_cls = BookFile.get_extractor(extension)
                if not extractor_cls:
                    return None
                
                content = zf.read(inner_filename)
                extractor = extractor_cls()
                extractor.load_from_stream(io.BytesIO(content))
                return extractor
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to extract book from ZIP {file_path}: {e}")
            return None
    else:
        extension = file_name.split('.')[-1].lower()
        extractor_cls = BookFile.get_extractor(extension)
        if not extractor_cls:
            return None
        
        extractor = extractor_cls()
        extractor.load_from_file(str(file_path))
        return extractor


def flatten_chapters(chapters: list[Any], index_start: int = 0) -> tuple[list[Any], int]:
    """Flatten a hierarchical list of chapters and assign a flat_index to each.

    Args:
        chapters: Hierarchical list of chapter objects.
        index_start: Starting index for flattening.

    Returns:
        A tuple: (flat_list, next_available_index)
    """
    flat_list = []
    current_index = index_start
    for chapter in chapters:
        chapter.flat_index = current_index
        flat_list.append(chapter)
        current_index += 1
        sub_flat, next_index = flatten_chapters(chapter.subchapters, current_index)
        flat_list.extend(sub_flat)
        current_index = next_index
    return flat_list, current_index


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename according to NLeech Styleguide:

    1. Support extended ASCII characters (e.g. Cyrillic).
    2. Using only word characters, underscores, hyphens, and dots.
    3. Forbidding spaces (replacing them with underscores).
    4. Replace multiple underscores with a single one.
    5. Strip leading/trailing ._-

    Args:
        filename: The filename to sanitize.

    Returns:
        The sanitized filename.
    """
    # Replace colons with ' - ' to separate Author/Title if they were using colons
    filename = filename.replace(':', ' - ')
    # Replace spaces with underscores
    filename = filename.replace(' ', '_')
    # Use Django's get_valid_filename to remove basic invalid characters
    filename = get_valid_filename(filename)
    # Apply final whitelist filter ([^\w._-]) to allow word characters (including Cyrillic)
    filename = re.sub(r'[^\w._-]', '_', filename)
    # Replace multiple underscores with a single one
    filename = re.sub(r'_+', '_', filename)
    # Strip leading/trailing ._-
    return filename.strip('._-')


def get_book_file_content(book: 'Book') -> tuple[str | None, bytes | None, str | None]:
    """Get the unzipped content of a book file.

    Args:
        book: The Book model instance.

    Returns:
        A tuple of (filename, content bytes, content_type).
    """
    if not book.file:
        return None, None, None

    file_path = Path(book.file.path)
    file_name = book.file.name.lower()

    # Register custom mimetypes if not present
    if not mimetypes.types_map.get('.epub'):
        mimetypes.add_type('application/epub+zip', '.epub')
    if not mimetypes.types_map.get('.fb2'):
        mimetypes.add_type('application/x-fictionbook+xml', '.fb2')

    # Generate standardized filename base: str(Author) - str(title)
    # Following FirstAuthor_et_al_-_Title for multiple authors
    authors = list(book.authors.all())
    if not authors:
        author_part = 'Unknown'
    elif len(authors) > 1:
        author_part = f'{authors[0]}_et_al'
    else:
        author_part = str(authors[0])

    filename_base = f'{author_part} - {book.title}'

    if file_name.endswith('.zip'):
        try:
            with pyzipper.AESZipFile(file_path) as zf:
                zf.setpassword(settings.BOOK_PWD)
                namelist = zf.namelist()
                if not namelist:
                    return None, None, None

                # Assume the first file is the book content
                inner_filename = namelist[0]
                content = zf.read(inner_filename)
                content_type, _ = mimetypes.guess_type(inner_filename)
                
                # Use extension from inner file, lowercase it
                ext = Path(inner_filename).suffix
                sanitized_filename = sanitize_filename(filename_base) + ext.lower()
                
                return sanitized_filename, content, content_type or 'application/octet-stream'
        except Exception as e:
            logging.getLogger(__name__).error(f'Failed to extract book from ZIP {file_path}: {e}')
            return None, None, None
    else:
        # Not a zip, just read the file
        try:
            content = file_path.read_bytes()
            content_type, _ = mimetypes.guess_type(file_name)
            
            # Use extension from original file, lowercase it
            ext = file_path.suffix
            sanitized_filename = sanitize_filename(filename_base) + ext.lower()
            
            return sanitized_filename, content, content_type or 'application/octet-stream'
        except Exception as e:
            logging.getLogger(__name__).error(f'Failed to read book file {file_path}: {e}')
            return None, None, None
