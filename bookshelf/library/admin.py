from django.contrib import admin
from django.utils.html import format_html
from imagekit.admin import AdminThumbnail

from .models import (
    Language, Author, BookSeries, Genre, GenreName, Book, BookSeriesLink
)


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
    search_fields = ('name', 'code')
    inlines = [SubGenreAdminInline, GenreNameInline]


class BookSeriesBookInline(admin.TabularInline):
    model = BookSeriesLink
    extra = 0
    verbose_name = 'Book'
    verbose_name_plural = 'Books'
    fields = ('get_cover_preview', 'book', 'sequence_number')
    readonly_fields = ('get_cover_preview', 'book')
    show_change_link = True
    ordering = ('sequence_number',)

    def get_cover_preview(self, obj):
        if obj.book.cover:
            return format_html('<img src="{}" style="max-height: 100px;"/>', obj.book.cover_preview.url)
        return 'No cover'
    get_cover_preview.short_description = 'Cover preview'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('book')


class BookSeriesAdmin(admin.ModelAdmin):
    search_fields = ('name',)
    inlines = [SubSeriesAdminInline, BookSeriesBookInline]


class BookSeriesLinkInline(admin.TabularInline):
    model = BookSeriesLink
    extra = 1
    autocomplete_fields = ('series',)


class BookAdmin(admin.ModelAdmin):
    cover_thumbnail = AdminThumbnail(image_field='cover_preview')
    list_display = ('title', 'language')
    readonly_fields = ('cover_thumbnail',)
    autocomplete_fields = ('authors', 'genres')
    inlines = [BookSeriesLinkInline]
    search_fields = ('title', 'isbn')


admin.site.register(Language)

admin.site.register(Genre, GenreAdmin)
admin.site.register(GenreName)

admin.site.register(Author, AuthorAdmin)

admin.site.register(BookSeries, BookSeriesAdmin)

admin.site.register(Book, BookAdmin)
