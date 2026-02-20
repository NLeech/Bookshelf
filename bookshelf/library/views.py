import string

from django.shortcuts import render
from django.views import generic
from django.conf import settings

from .models import Author

# Create your views here.
class HomePageView(generic.TemplateView):
    template_name = 'library/index.html'


class AuthorListView(generic.ListView):
    model = Author
    template_name = 'library/author_list.html'
    context_object_name = 'authors'
    paginate_by = settings.PAGINATE_BY

    def get_queryset(self):
        filter_string = self.request.GET.get('filter', '')
        if filter_string:
            return Author.objects.filter(last_name__startswith=filter_string).prefetch_related('books')
        else:
            return Author.objects.prefetch_related('books')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['alphabet'] = string.ascii_uppercase
        context['filter'] = self.request.GET.get('filter', '')
        return context

    def render_to_response(self, context, **response_kwargs):
        """
        Check if it's an AJAX/HTMX request.
        If so, append the partial fragment to the template name.
        """
        if self.request.headers.get('HX-Request'):
            # This targets 'authors_list.html#book-list'
            self.template_name = f"{self.template_name}#authors_list-result"

        return super().render_to_response(context, **response_kwargs)
    