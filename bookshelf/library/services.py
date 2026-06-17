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

from .models import Author, Genre, Language, Book, BookSeries
from .book_utils.book_file import BookFile


# Custom MIME types for book formats not present in the system mime database.
# Keyed by the canonical extension (leading dot, lowercase).
CUSTOM_MIME_TYPES = {
    '.epub': 'application/epub+zip',
    '.fb2': 'application/x-fictionbook+xml',
}

DEFAULT_CONTENT_TYPE = 'application/octet-stream'


def _register_custom_mimetypes() -> None:
    """Register book-specific MIME types with the ``mimetypes`` module.

    ``.epub`` and ``.fb2`` are not reliably present in the host mime database,
    so they are added explicitly (idempotently) before any lookup.
    """
    for ext, content_type in CUSTOM_MIME_TYPES.items():
        if not mimetypes.types_map.get(ext):
            mimetypes.add_type(content_type, ext)


def get_content_type(name_or_format: str) -> str:
    """Return the MIME content type for a filename, extension, or format tag.

    Accepts a full filename (``'book.fb2'``), an extension (``'.fb2'`` or
    ``'fb2'``), or a bare format tag (``'fb2'``).  Ensures the book-specific
    types (EPUB, FB2) are registered before delegating to
    ``mimetypes.guess_type``.  Falls back to ``application/octet-stream`` when
    the type cannot be determined.

    Args:
        name_or_format: A filename, extension, or format tag.

    Returns:
        The MIME type string, or ``application/octet-stream`` if unknown.
    """
    _register_custom_mimetypes()

    name = (name_or_format or '').lower().strip()
    if not name:
        return DEFAULT_CONTENT_TYPE

    # Normalise a bare extension ('.fb2') or format tag ('fb2') into a
    # synthetic filename so ``guess_type`` resolves it.  ``guess_type('.fb2')``
    # treats the value as a dotfile name and returns nothing, so we always
    # build a name with a real stem when no path separator is present.
    if '/' not in name and '\\' not in name:
        ext = name if name.startswith('.') else f'.{name.rsplit(".", 1)[-1]}'
        name = f'x{ext}'

    content_type, _ = mimetypes.guess_type(name)
    return content_type or DEFAULT_CONTENT_TYPE


@dataclass(order=True)
class AlphabetTree:
    """
    A tree structure for storing authors grouped by the first letters of their last names.
    """
    name: str = field(compare=True)
    filter: str = field(default='', compare=False, repr=True)
    regex: str = field(default='', compare=False, repr=False)
    quantity: int = field(default=0, compare=False, repr=True)
    entries: list['AlphabetTree'] = field(default_factory=list, compare=False, repr=False)

    def __str__(self) -> str:
        return f'{self.name.capitalize()}'


def _recursive_defaultdict(depth: int) -> defaultdict[str, Any]:
    """Create a recursive defaultdict for storing the tree structure.

    Args:
        depth: Depth of the tree (number of levels).

    Returns:
        A defaultdict with the specified depth.
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
    """Recursively make the tree structure for a given prefix and quantity.

    Args:
        prev_level: The level of the tree to which the prefix should be added.
        prefix: Full prefix of the last name (up to max_level characters)
            for which the quantity is calculated.
        quantity: Quantity of authors with the given prefix.
        level: Level of the tree to which the prefix should be added (starting from 2).
        max_level: Maximum depth of the tree.
    """
    current_prefix = prefix[:level]
    prev_level['sub'][current_prefix]['total'] += quantity

    if len(prefix) > level and prefix[level].isalpha():
        if level < max_level:
            _add_prefix_level(prev_level['sub'][current_prefix], prefix, quantity, level + 1, max_level)
    else:
        prev_level['sub'][current_prefix]['star'] += quantity


def _build_tree_node(parent: AlphabetTree, prefix: str, data: dict[str, Any], min_quantity: int) -> None:
    """Recursively build the alphabet tree from aggregated prefix data.

    Args:
        parent: The parent node to attach children to.
        prefix: The current prefix string for this node.
        data: Dict with 'total', 'star', and optionally 'sub' keys.
        min_quantity: Threshold above which a node is expanded further.
    """
    node = AlphabetTree(name=prefix, filter=prefix, quantity=data['total'])
    parent.entries.append(node)

    if node.quantity <= min_quantity or 'sub' not in data:
        return

    for sub_prefix in sorted(data['sub'].keys()):
        _build_tree_node(node, sub_prefix, data['sub'][sub_prefix], min_quantity)

    if data['star'] > 0:
        node.entries.append(AlphabetTree(
            name=prefix + '*',
            filter='',
            regex=fr'^{prefix}([^[:alpha:]].*)?$',
            quantity=data['star']
        ))


def get_alphabet_tree(
    queryset: QuerySet,
    field_name: str,
    max_tree_depth: int = 3,
    min_quantity: int = 50,
    min_first_level_quantity: int = 10
) -> AlphabetTree:
    """Get a tree structure for storing items grouped by the first letters of a specific field.

    Tree example:
    - a
        - aa (items with field_name starting with 'aa')
            - aaa (items with field_name starting with 'aaa')
            - aab (items with field_name starting with 'aab')
            - aa* (only non-alpha after 'aa' or nothing after 'aa')
        - ab (items with field_name starting with 'ab')
        - a* (only non-alpha after 'a' or nothing after 'a')
    - b

    ...

    - 0-9 (all digits prefixes)
    - other
        - * (all non-alpha prefixes)
        - ы (alpha prefixes with quantity < min_first_level_quantity)

    The tree is built in a way that if the number of items in a branch is greater than min_quantity,
    the branch is expanded to the next level.
    The tree is built up to max_tree_depth levels. max_tree_depth should be at least 1, otherwise it will be set to 1.

    Args:
        queryset: The queryset to aggregate.
        field_name: The field to group by (e.g., 'last_name' for authors, 'title' for books).
        max_tree_depth: Max depth of the tree.
        min_quantity: Threshold above which a node is expanded further.
        min_first_level_quantity: Threshold for first level nodes. If less, the node is moved to 'other'.

    Returns:
        The root of the tree.
    """

    max_tree_depth = max(1, max_tree_depth)
    lower_field = Lower(field_name)

    # Get all prefix counts up to max_tree_depth for each category
    counts = (
        queryset
        .annotate(
            category=Case(
                When(**{f'{field_name}__regex': r'^[[:alpha:]]'}, then=Value('alpha')),
                When(**{f'{field_name}__regex': r'^[0-9]'}, then=Value('digit')),
                default=Value('other'),
                output_field=CharField(),
            ),
            prefix=Left(lower_field, max_tree_depth)
        )
        .values('category', 'prefix')
        .annotate(quantity=Count('id'))
    )

    # Intermediate storage for aggregation
    level1_data = _recursive_defaultdict(max_tree_depth)

    digit_count = 0
    other_count = 0

    for item in counts:
        category = item['category']
        prefix = item['prefix']
        quantity = item['quantity']

        # empty field value
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

    # 1. Non-alpha items go to other_node
    if other_count > 0:
        other_node.entries.append(AlphabetTree(
            name='* (all non-alpha)',
            filter='',
            regex=r'^[^[:alpha:][:digit:]]',
            quantity=other_count,
        ))
        other_node.quantity += other_count

    # Alpha nodes: high-quantity go to root, low-quantity go to other_node
    moved_prefixes = []
    for p1 in sorted(level1_data.keys()):
        if level1_data[p1]['total'] >= min_first_level_quantity:
            _build_tree_node(root, p1, level1_data[p1], min_quantity)
        else:
            _build_tree_node(other_node, p1, level1_data[p1], min_quantity)
            other_node.quantity += level1_data[p1]['total']
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
            quantity=digit_count,
        ))

    if other_node.entries:
        root.entries.append(other_node)

    return root


def find_alphabet_node_by_name(root: AlphabetTree, name: str) -> AlphabetTree | None:
    """Depth-first search for the tree node whose .name == name; None if absent.

    Used by tree views to resolve ``…/tree/<name>/`` path segments.

    Args:
        root: The tree node to start the search from.
        name: Exact node name to look for (case-sensitive).

    Returns:
        The first matching AlphabetTree node, or None if not found.
    """
    if root.name == name:
        return root
    for child in root.entries:
        found = find_alphabet_node_by_name(child, name)
        if found is not None:
            return found
    return None


def find_alphabet_node(node: AlphabetTree, filter_val: str, regex_val: str) -> AlphabetTree | None:
    """Recursively find a node in the alphabet tree that matches the given filter or regex.

    The search is case-insensitive for filter_val.

    Args:
        node: The tree node to start search from.
        filter_val: The filter string to match.
        regex_val: The regex string to match.

    Returns:
        The matching AlphabetTree node or None if no match is found.
    """
    if (filter_val or regex_val):
        if regex_val and node.regex == regex_val:
            return node
        if filter_val and node.filter.lower() == filter_val.lower():
            return node

    for entry in node.entries:
        res = find_alphabet_node(entry, filter_val, regex_val)
        if res:
            return res

    return None


def get_languages(queryset: QuerySet[Book]) -> QuerySet[Language]:
    """Get all languages of the books in the provided queryset.

    Each language is annotated with the count of books in that language within the queryset.

    Args:
        queryset: The Book queryset to get languages for.

    Returns:
        A QuerySet of Language objects annotated with book_count.
    """
    return (
        Language.objects
        .filter(books__in=queryset)
        .annotate(book_count=Count('books', filter=Q(books__in=queryset)))
        .order_by('name')
        .distinct()
    )


def get_genres_tree(queryset: QuerySet[Book]) -> list[dict[str, Any]]:
    """Build a hierarchical tree of genres associated with the books in the provided queryset.

    Includes ancestor genres even if they don't have books directly.
    The tree is sorted alphabetically at each level and includes the count of books for each genre.

    Args:
        queryset: The Book queryset to build the genre tree for.

    Returns:
        A list of dicts with keys: 'genre' (Genre object), 'book_count' (int),
        and 'children' (list of dicts).
    """
    # Get all genres directly associated with the books in the queryset, with book counts
    direct_genres_qs = (
        Genre.objects
        .filter(books__in=queryset)
        .annotate(book_count=Count('books', filter=Q(books__in=queryset)))
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


def get_author_languages(author: Author) -> QuerySet[Language]:
    """Get all languages of the books written by the author.

    Each language is annotated with the count of books by this author in that language.

    Args:
        author: The Author instance to get languages for.

    Returns:
        A QuerySet of Language objects annotated with book_count.
    """
    return get_languages(author.books.all())


def get_author_genres_tree(author: Author) -> list[dict[str, Any]]:
    """Build a hierarchical tree of genres associated with the author's books.

    Includes ancestor genres even if they don't have books directly.
    The tree is sorted alphabetically at each level and includes the count of books for each genre.

    Args:
        author: The Author instance to build the genre tree for.

    Returns:
        A list of dicts with keys: 'genre' (Genre object), 'book_count' (int),
        and 'children' (list of dicts).
    """
    return get_genres_tree(author.books.all())


def get_book_extractor(book: Book) -> BookFile | None:
    """Load the appropriate book extractor based on the file extension.

    Handles password-protected ZIP files if necessary.

    Args:
        book: The Book model instance.

    Returns:
        An instance of EpubBookFile, Fb2BookFile, or None if unsupported.
    """
    if not book.file:
        return None

    file_name = book.file.name.lower()

    try:
        file_data = book.file.read()
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to read book file {book.file.name}: {e}")
        return None
    finally:
        book.file.close()

    if file_name.endswith('.zip'):
        try:
            with pyzipper.AESZipFile(io.BytesIO(file_data)) as zf:
                zf.setpassword(settings.BOOK_PWD)
                namelist = zf.namelist()
                if not namelist:
                    return None

                # Assume the first file is the book content
                inner_filename = namelist[0]
                extension = Path(inner_filename).suffix.removeprefix('.').lower()
                extractor_cls = BookFile.get_extractor(extension)
                if not extractor_cls:
                    return None

                content = zf.read(inner_filename)
                extractor = extractor_cls()
                extractor.load_from_stream(io.BytesIO(content))
                return extractor
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to extract book from ZIP {book.file.name}: {e}")
            return None
    else:
        extension = Path(file_name).suffix.removeprefix('.').lower()
        extractor_cls = BookFile.get_extractor(extension)
        if not extractor_cls:
            return None

        extractor = extractor_cls()
        extractor.load_from_stream(io.BytesIO(file_data))
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
    """Sanitize a filename to be safe for use in file systems, 
    while allowing word characters (including Cyrillic), dots, underscores, and hyphens.

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

    file_name = book.file.name.lower()

    # Register custom mimetypes if not present
    _register_custom_mimetypes()

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

    try:
        file_data = book.file.read()
    except Exception as e:
        logging.getLogger(__name__).error(f'Failed to read book file {book.file.name}: {e}')
        return None, None, None
    finally:
        book.file.close()

    if file_name.endswith('.zip'):
        try:
            with pyzipper.AESZipFile(io.BytesIO(file_data)) as zf:
                zf.setpassword(settings.BOOK_PWD)
                namelist = zf.namelist()
                if not namelist:
                    return None, None, None

                # Assume the first file is the book content
                inner_filename = namelist[0]
                content = zf.read(inner_filename)
                content_type = get_content_type(inner_filename)

                # Use extension from inner file, lowercase it
                ext = Path(inner_filename).suffix
                sanitized_filename = sanitize_filename(filename_base) + ext.lower()

                return sanitized_filename, content, content_type
        except Exception as e:
            logging.getLogger(__name__).error(f'Failed to extract book from ZIP {book.file.name}: {e}')
            return None, None, None
    else:
        # Not a zip, just return the file data
        content_type = get_content_type(file_name)

        # Use extension from original file, lowercase it
        ext = Path(file_name).suffix
        sanitized_filename = sanitize_filename(filename_base) + ext.lower()

        return sanitized_filename, file_data, content_type


def search_entities(query: str) -> dict[str, Any]:
    """Search for authors, books, and series by query string.

    Args:
        query: The search query string.

    Returns:
        A dictionary containing search results and counts for each entity type.
    """
    if not query:
        return {
            'authors': Author.objects.none(),
            'books': Book.objects.none(),
            'series': BookSeries.objects.none(),
            'authors_count': 0,
            'books_count': 0,
            'series_count': 0,
            'total_count': 0,
        }

    authors = Author.objects.filter(
        Q(first_name__icontains=query) |
        Q(middle_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(nickname__icontains=query)
    ).distinct().order_by('last_name', 'first_name', 'middle_name')

    books = Book.objects.filter(
        title__icontains=query
    ).prefetch_related('authors').distinct().order_by('title')

    series = BookSeries.objects.filter(
        name__icontains=query
    ).distinct().order_by('name')

    authors_count = authors.count()
    books_count = books.count()
    series_count = series.count()

    return {
        'authors': authors,
        'books': books,
        'series': series,
        'authors_count': authors_count,
        'books_count': books_count,
        'series_count': series_count,
        'total_count': authors_count + books_count + series_count,
    }


def get_descendants(parent_ids: list[int]) -> set[int]:
    """ Recursively get all descendant genre IDs for the given parent genre IDs.
    
    Args:
        parent_ids: A list of genre ID.

    Returns: A set of descendant genre IDs.
    """
    descendant_ids = set()
    children = Genre.objects.filter(parent_id__in=parent_ids).values_list('id', flat=True)

    for item in children:
        # get only children without descendants (end nodes)
        item_descendants_ids = get_descendants([item])
        if item_descendants_ids:
            descendant_ids.update(item_descendants_ids)
        else:
            descendant_ids.add(item)

    return descendant_ids