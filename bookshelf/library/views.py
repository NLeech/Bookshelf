import string

from django.shortcuts import render
from django.views import generic
from django.conf import settings

from .models import Author
from .sevices import get_alphabet_tree

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
        regex_string = self.request.GET.get('regex', '')

        qs = Author.objects.prefetch_related('books')

        if regex_string:
            return qs.filter(last_name__iregex=regex_string)
        elif filter_string:
            return qs.filter(last_name__istartswith=filter_string)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['alphabet_tree'] = get_alphabet_tree()
        context['filter'] = self.request.GET.get('filter', '')
        context['regex'] = self.request.GET.get('regex', '')
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
    
class AuthorDetailView(generic.DetailView):
    model = Author
    template_name = 'library/author_details.html'