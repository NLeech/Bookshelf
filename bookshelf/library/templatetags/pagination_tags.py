from django import template
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
