from django.contrib import admin

from library.models import Language, Author, BookSeries, BookSeriesName, Genre, Book


class AuthorAdmin(admin.ModelAdmin):
    fields = ('last_name', 'first_name', 'middle_name', 'main_author')
    ordering = ('last_name',)

    list_display = ('id', 'last_name', 'first_name', 'middle_name', 'main_author')
    list_display_links = ('id', 'last_name', 'first_name', 'middle_name', 'main_author')

    search_fields = ('id', 'last_name', 'middle_name', 'first_name',)

    autocomplete_fields = ('main_author',)
    list_select_related = ('main_author',)

    def get_queryset(self, request):
        # add filter for autocomplete field 'main_author'
        # The author cannot be linked to another author who is already linked to the main author.
        if request.GET.get('field_name') == 'main_author':
            return super().get_queryset(request).filter(main_author=None).select_related('main_author')

        return super().get_queryset(request).select_related('main_author')


admin.site.register(Language)
admin.site.register(Genre)
admin.site.register(Author, AuthorAdmin)
admin.site.register(BookSeries)
admin.site.register(BookSeriesName)
admin.site.register(Book)


