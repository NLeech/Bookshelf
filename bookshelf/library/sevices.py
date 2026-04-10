import logging
from collections import defaultdict
from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import Count, Case, When, Value, CharField
from django.db.models.functions import Left, Lower

from library.models import Author, Genre


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

    def __str__(self):
        return f'{self.name.capitalize()}'


def _recursive_defaultdict(depth: int) -> defaultdict:
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


def _add_prefix_level(prev_level: defaultdict, prefix: str, quantity: int, level: int, max_level) -> None:
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


def _build_tree_node(parent: AlphabetTree, prefix: str, data: dict, min_quantity: int) -> None:
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
