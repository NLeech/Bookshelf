from django import template
from typing import Any

register = template.Library()

@register.filter
def has_selected_genre(node: dict[str, Any], selected_genres: list[str]) -> bool:
    """Recursively check if a  of its descendants are selected.

    Args:
        node: A dictionary representing a genre tree node (from get_genres_tree).
        selected_genres: A list of selected genre codes.

    Returns:
        True if the current node's genre or any of its children are in selected_genres.
    """

    def _has_selected_child(node: dict[str, Any], selected_genres: list[str]) -> bool:
        # Check the current node 
        if node['genre'].code in selected_genres:
            return True

        # Recursively check children
        for child in node.get('children', []):
            if _has_selected_child(child, selected_genres):
                return True


    if not selected_genres:
        return False

    # Check the current node 
    if node['genre'].code in selected_genres:
        return False

    # Recursively check children
    for child in node.get('children', []):
        if _has_selected_child(child, selected_genres):
            return True

    return False
