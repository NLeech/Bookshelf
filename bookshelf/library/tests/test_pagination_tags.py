from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase

from library.templatetags.pagination_tags import elided_page_range


class ElidedPageRangeTagTest(TestCase):
    """Unit tests for the ``elided_page_range`` template tag."""

    @classmethod
    def setUpTestData(cls):
        # 20 pages of 10 items each.
        cls.paginator = Paginator(list(range(1, 201)), 10)
        cls.ellipsis = cls.paginator.ELLIPSIS

    def test_returns_all_pages_when_short(self):
        """A range short enough to fit is returned in full, without ellipsis."""
        paginator = Paginator(list(range(1, 21)), 10)  # 2 pages
        result = list(elided_page_range(paginator.page(1)))

        self.assertEqual(result, [1, 2])

    def test_collapses_middle_with_ellipsis_on_both_sides(self):
        """A middle page keeps the ends, the current window, and elides the rest."""
        result = list(elided_page_range(self.paginator.page(10)))

        self.assertEqual(result[0], 1)
        self.assertEqual(result[-1], 20)
        self.assertEqual(result.count(self.ellipsis), 2)
        # Window with the default on_each_side=2 around page 10.
        for num in (8, 9, 10, 11, 12):
            self.assertIn(num, result)
        # A far page is collapsed away, not rendered.
        self.assertNotIn(5, result)

    def test_no_left_ellipsis_near_start(self):
        """Edge: near the first page only the right side is elided."""
        result = list(elided_page_range(self.paginator.page(2)))

        self.assertEqual(result[0], 1)
        self.assertEqual(result.count(self.ellipsis), 1)

    def test_custom_window_args_narrow_the_range(self):
        """Edge: on_each_side/on_ends are passed through to the paginator."""
        result = list(
            elided_page_range(self.paginator.page(10), on_each_side=1, on_ends=1)
        )

        for num in (9, 10, 11):
            self.assertIn(num, result)
        self.assertNotIn(8, result)
        self.assertNotIn(12, result)


class PaginationPartialRenderTest(TestCase):
    """The shared pagination partial renders the elided range end to end."""

    def setUp(self):
        self.request = RequestFactory().get('/books/')
        # 20 pages, current is the middle one.
        self.page_obj = Paginator(list(range(1, 201)), 10).page(10)

    def _render(self):
        return render_to_string(
            'library/include/pagination.html',
            {'page_obj': self.page_obj},
            request=self.request,
        )

    def test_renders_ellipsis_and_windowed_links(self):
        """Window pages and both ends appear; collapsed pages and full range do not."""
        html = self._render()

        self.assertIn('…', html)  # Paginator.ELLIPSIS marker
        self.assertIn('page=1"', html)  # first end
        self.assertIn('page=20"', html)  # last end
        self.assertIn('page=8"', html)  # window edge
        self.assertIn('page=12"', html)  # window edge
        self.assertNotIn('page=5"', html)  # collapsed
        self.assertNotIn('page=16"', html)  # collapsed

    def test_current_page_is_active_and_not_a_link(self):
        """The current page renders as an active span, never as a link."""
        html = self._render()

        self.assertIn('page-item active', html)
        self.assertNotIn('page=10"', html)
