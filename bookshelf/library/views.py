import string
import io

from datetime import timedelta
from collections import defaultdict
from django.http import FileResponse, HttpRequest, Http404
from django.shortcuts import render, get_object_or_404
from django.views import generic
from django.conf import settings
from django.db.models import Prefetch, Q
from django.utils import timezone
from django.core.paginator import Paginator
from django.urls import reverse

from .models import Author, BookSeriesLink, Book, Genre, Language
from .services import (
    get_alphabet_tree,
    get_languages,
    get_genres_tree,
    get_author_languages,
    get_author_genres_tree,
    get_book_extractor,
    get_book_file_content,
    flatten_chapters,
    find_alphabet_node,
    search_entities
)


class HomePageView(generic.TemplateView):
    template_name = 'library/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        q = self.request.GET.get('q', '')
        context['query'] = q

        if 'q' in self.request.GET:
            context['search_results'] = search_entities(q)

        seven_days_ago = timezone.now() - timedelta(days=7)

        latest_books_qs = Book.objects.filter(
            created_at__gte=seven_days_ago
        ).only(
            'id', 'title', 'created_at', 'description', 'cover', 'file', 'file_type', 'size'
        ).order_by('-created_at', 'title')

        paginator = Paginator(latest_books_qs, settings.PAGINATE_BY)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context['latest_books'] = page_obj.object_list
        context['page_obj'] = page_obj

        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('HX-Request'):
            if context.get('query'):
                self.template_name = 'library/include/search_results.html'
            else:
                # If query is empty, remove the search results block
                if 'q' in self.request.GET:
                    self.template_name = 'library/include/search_results.html'
                else:
                    self.template_name = f"{self.template_name}#latest_arrivals"
        return super().render_to_response(context, **response_kwargs)


class BookDownloadView(generic.View):
    def get(self, request: HttpRequest, pk: int) -> FileResponse:

        book = get_object_or_404(Book, pk=pk)
        filename, content, content_type = get_book_file_content(book)

        if not content:
            raise Http404('Book file not found or could not be extracted.')

        return FileResponse(
            io.BytesIO(content),
            as_attachment=True,
            filename=filename,
            content_type=content_type
        )


class AuthorListView(generic.ListView):
    model = Author
    template_name = 'library/author_list.html'
    context_object_name = 'authors'
    paginate_by = settings.PAGINATE_BY

    def get_queryset(self):
        filter_string = self.request.GET.get('filter', '')
        regex_string = self.request.GET.get('regex', '')

        qs = Author.objects.prefetch_related('books')

        if regex_string:
            return qs.filter(last_name__iregex=regex_string)
        elif filter_string:
            return qs.filter(last_name__istartswith=filter_string)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['alphabet_tree'] = get_alphabet_tree(Author.objects.all(), 'last_name')
        context['filter'] = self.request.GET.get('filter', '')
        context['regex'] = self.request.GET.get('regex', '')
        return context

    def render_to_response(self, context, **response_kwargs):
        """
        Check if it's an AJAX/HTMX request.
        If so, append the partial fragment to the template name.
        """
        if self.request.headers.get('HX-Request'):
            self.template_name = f"{self.template_name}#authors_list-result"

        return super().render_to_response(context, **response_kwargs)


class AuthorDetailView(generic.DetailView):
    model = Author
    template_name = 'library/author.html'
    context_object_name = 'author'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        author = self.get_object()
        tab = self.request.GET.get('tab', 'alpha')
        context['active_tab'] = tab

        # Get filter parameters
        selected_langs = self.request.GET.getlist('lang')
        selected_genres = self.request.GET.getlist('genre')
        context['selected_langs'] = selected_langs
        context['selected_genres'] = selected_genres

        # Base queryset for books with common prefetches
        books_qs = author.books.all()

        # Apply filters
        if selected_langs:
            books_qs = books_qs.filter(language__code__in=selected_langs)
        if selected_genres:
            books_qs = books_qs.filter(genres__code__in=selected_genres)

        if selected_langs or selected_genres:
            books_qs = books_qs.distinct()

        # Filter options for the sidebar
        context['available_languages'] = get_author_languages(author)
        context['available_genres_tree'] = get_author_genres_tree(author)

        if tab == 'alpha':
            context['books_alpha'] = books_qs.order_by('title').prefetch_related('authors')
        elif tab == 'recent':
            context['books_recent'] = books_qs.order_by('-created_at').prefetch_related('authors')
        elif tab == 'series':
            # Prefetch the series links for all books of this author
            books = list(books_qs.prefetch_related('bookserieslink_set__series', 'authors'))

            series_map = defaultdict(list)
            standalone_books = []

            for book in books:
                links = book.bookserieslink_set.all()
                if not links:
                    standalone_books.append(book)
                else:
                    for link in links:
                        series_map[link.series].append({
                            'book': book,
                            'seq': link.sequence_number
                        })

            # Format series for template
            series_list = []
            for series, items in series_map.items():
                items.sort(key=lambda x: x['seq'])
                series_list.append({
                    'series': series,
                    'books_info': items,
                    'count': len(items)
                })
            series_list.sort(key=lambda x: x['series'].name.lower())

            context['series_list'] = series_list
            context['standalone_books'] = sorted(standalone_books, key=lambda b: b.title.lower())
            context['standalone_count'] = len(standalone_books)

        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('HX-Request'):
            tab = self.request.GET.get('tab', 'alpha')
            # Select the appropriate block based on the tab
            self.template_name = f"{self.template_name}#{tab}_tab"
        return super().render_to_response(context, **response_kwargs)


class BookListView(generic.ListView):
    model = Book
    template_name = 'library/book_list.html'
    context_object_name = 'books'
    paginate_by = settings.PAGINATE_BY

    def get_queryset(self):
        qs = Book.objects.prefetch_related('authors').distinct()

        selected_langs = self.request.GET.getlist('lang')
        selected_genres = self.request.GET.getlist('genre')
        filter_string = self.request.GET.get('filter', '')
        regex_string = self.request.GET.get('regex', '')

        if selected_langs:
            qs = qs.filter(language__code__in=selected_langs)

        if selected_genres:
            # Plan says: "including subgenres"
            genre_ids = Genre.objects.filter(code__in=selected_genres).values_list('id', flat=True)
            descendant_ids = set()

            def get_descendants(parent_ids):
                children = Genre.objects.filter(parent_id__in=parent_ids).values_list('id', flat=True)
                if children:
                    descendant_ids.update(children)
                    get_descendants(children)

            get_descendants(genre_ids)
            all_genre_ids = set(genre_ids) | descendant_ids
            qs = qs.filter(genres__id__in=all_genre_ids)

        if regex_string:
            qs = qs.filter(title__iregex=regex_string)
        elif filter_string:
            qs = qs.filter(title__istartswith=filter_string)

        return qs.order_by('title')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Sidebar aggregates
        context['available_languages'] = get_languages(Book.objects.all())
        context['available_genres_tree'] = get_genres_tree(Book.objects.all())
        alphabet_tree = get_alphabet_tree(Book.objects.all(), 'title')
        context['alphabet_tree'] = alphabet_tree

        selected_lang_codes = self.request.GET.getlist('lang')
        selected_genre_codes = self.request.GET.getlist('genre')

        context['selected_langs'] = selected_lang_codes
        context['selected_genres'] = selected_genre_codes

        if selected_lang_codes:
            context['active_languages'] = Language.objects.filter(code__in=selected_lang_codes)
        if selected_genre_codes:
            context['active_genres'] = Genre.objects.filter(code__in=selected_genre_codes)

        filter_val = self.request.GET.get('filter', '')
        regex_val = self.request.GET.get('regex', '')
        context['filter'] = filter_val
        context['regex'] = regex_val

        if filter_val or regex_val:
            context['active_alphabet_node'] = find_alphabet_node(alphabet_tree, filter_val, regex_val)

        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('HX-Request'):
            self.template_name = f"{self.template_name}#books_list-result"
        return super().render_to_response(context, **response_kwargs)


class BookDetailView(generic.DetailView):
    model = Book
    template_name = 'library/book.html'
    context_object_name = 'book'

    def get_queryset(self):
        return super().get_queryset().prefetch_related('authors')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        book = self.get_object()
        chapter_index = self.kwargs.get('chapter_index', 0)

        extractor = get_book_extractor(book)
        if extractor:
            chapters = extractor.chapters
            flat_chapters, _ = flatten_chapters(chapters)

            context['chapters'] = chapters  # Original hierarchical list for TOC
            if not (0 <= chapter_index < len(flat_chapters)):
                chapter_index = 0

            if flat_chapters:
                context['current_chapter'] = flat_chapters[chapter_index]
                if chapter_index > 0:
                    context['prev_chapter'] = flat_chapters[chapter_index - 1]
                if chapter_index < len(flat_chapters) - 1:
                    context['next_chapter'] = flat_chapters[chapter_index + 1]
            else:
                context['current_chapter'] = None

        return context

    def render_to_response(self, context, **response_kwargs):
        """
        Check if it's an AJAX/HTMX request.
        If so, append the partial fragment to the template name.
        """
        if self.request.headers.get('HX-Request'):
            self.template_name = f"{self.template_name}#book_content"
        return super().render_to_response(context, **response_kwargs)
