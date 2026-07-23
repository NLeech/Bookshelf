from collections.abc import Iterator

from django import template
from django.core.paginator import Page
from django.utils.html import format_html_join

register = template.Library()


@register.simple_tag(takes_context=True)
def paginate_url(context, page_num, page_param="page", base_url=None):
    """
    Build a pagination URL, preserving existing query parameters.

    Copies the current request's GET parameters, sets the page parameter
    to the given value, and returns the full path with query string.

    Usage::

        {% paginate_url 1 p_param current_path as first_url %}
        <a href="{{ first_url }}">First</a>
    """
    request = context["request"]
    params = request.GET.copy()
    params[page_param] = page_num
    path = base_url or request.path
    return f"{path}?{params.urlencode()}"


@register.simple_tag
def elided_page_range(
    page_obj: Page, on_each_side: int = 2, on_ends: int = 1
) -> Iterator[int | str]:
    """
    Return the compact page range for a paginator ``Page``.

    Wraps ``Paginator.get_elided_page_range`` so the template iterates only
    the visible page numbers instead of the whole range. Yields page numbers
    interleaved with ``Paginator.ELLIPSIS`` markers where pages are collapsed.

    Args:
        page_obj: The current ``Page`` object.
        on_each_side: How many page numbers to show on each side of the
            current page.
        on_ends: How many page numbers to show at the first and last ends.

    Returns:
        An iterator of page numbers and ``Paginator.ELLIPSIS`` markers.

    Usage::

        {% elided_page_range page_obj as page_range %}
        {% for num in page_range %}...{% endfor %}
    """
    return page_obj.paginator.get_elided_page_range(
        page_obj.number, on_each_side=on_each_side, on_ends=on_ends
    )


@register.simple_tag(takes_context=True)
def preserve_querystring(context, exclude=""):
    """
    Generate hidden input fields for all current query parameters,
    excluding the specified parameter name.

    Useful inside GET forms that need to carry forward existing
    filter/search state while allowing one parameter to be set
    by the form itself.

    Usage::

        <form method="get">
            {% preserve_querystring 'page' %}
            <input type="number" name="page">
        </form>
    """
    request = context["request"]
    items = [
        (key, value) for key, value in request.GET.items() if key != exclude
    ]
    return format_html_join(
        "\n",
        '<input type="hidden" name="{}" value="{}">',
        items,
    )
