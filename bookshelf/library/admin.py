from django.contrib import admin

from .models import Language, Author, BookSeries, BookSeriesName, Genre, GenreName, Book


class GenreNameInline(admin.TabularInline):
    model = GenreName
    extra = 1

class SubGenreAdminInline(admin.StackedInline):
    model = Genre
    verbose_name_plural = 'Subgenres'
    fk_name = 'parent'
    show_change_link = True
    template = 'admin/edit_inline/header_only.html'
    fields = ()
    can_delete = False
    max_num = 0
    extra = 0

class SeriesNameInline(admin.TabularInline):
    model = BookSeriesName
    extra = 1


class SubSeriesAdminInline(admin.StackedInline):
    model = BookSeries
    verbose_name_plural = 'Subseries'
    fk_name = 'parent'
    show_change_link = True
    template = 'admin/edit_inline/header_only.html'
    fields = ()
    can_delete = False
    max_num = 0
    extra = 0


class SubAuthorAdminInline(admin.StackedInline):
    model = Author
    verbose_name_plural = 'Pseudonyms'
    fk_name = 'main_author'
    show_change_link = True
    template = 'admin/edit_inline/header_only.html'
    fields = ()
    can_delete = False
    max_num = 0
    extra = 0


class AuthorAdmin(admin.ModelAdmin):
    fields = ('last_name', 'first_name', 'middle_name', 'main_author')
    ordering = ('last_name',)

    list_display = ('id', 'last_name', 'first_name', 'middle_name', 'main_author')
    list_display_links = ('id', 'last_name', 'first_name', 'middle_name', 'main_author')

    search_fields = ('id', 'last_name', 'middle_name', 'first_name',)

    inlines = [SubAuthorAdminInline]

    autocomplete_fields = ('main_author',)
    list_select_related = ('main_author',)

    def get_queryset(self, request):
        # add a filter for autocomplete field 'main_author'
        # Author cannot be linked to another author who is already linked to the main author.
        if request.GET.get('field_name') == 'main_author':
            return super().get_queryset(request).filter(main_author=None).select_related('main_author')

        return super().get_queryset(request).select_related('main_author')


class GenreAdmin(admin.ModelAdmin):
    inlines = [SubGenreAdminInline, GenreNameInline]


class BookSeriesAdmin(admin.ModelAdmin):
    inlines = [SubSeriesAdminInline, SeriesNameInline]


admin.site.register(Language)

admin.site.register(Genre, GenreAdmin)
admin.site.register(GenreName)

admin.site.register(Author, AuthorAdmin)

admin.site.register(BookSeries, BookSeriesAdmin)
admin.site.register(BookSeriesName)

admin.site.register(Book)
