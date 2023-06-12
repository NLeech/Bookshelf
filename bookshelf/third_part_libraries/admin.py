from django.contrib import admin

from third_part_libraries.models import FlibustaAuthor, FlibustaGenre


class FlibustaAuthorInline(admin.StackedInline):
    model = FlibustaAuthor
    fk_name = 'main_author'
    # readonly_fields = ('FlibustaAuthor',)
    can_delete = False
    extra = 0

    # def has_add_permission(self, request, obj=None):
    #     return False
    #
    # def has_delete_permission(self, request, obj=None):
    #     return False


class FlibustaGenreAdmin(admin.ModelAdmin):
    fields = ('genre_code', 'genre_desc', 'genre_meta')
    ordering = ('id',)

    list_display = ('id', 'genre_code', 'genre_desc', 'genre_meta')
    list_display_links = ('id', 'genre_code', 'genre_desc', 'genre_meta')

    search_fields = ('id', 'genre_code', 'genre_desc', 'genre_meta')


class FlibustaAuthorAdmin(admin.ModelAdmin):
    fields = ('last_name', 'first_name', 'middle_name', 'main_author', 'library_author')
    ordering = ('id',)

    list_display = ('id', 'last_name', 'first_name', 'middle_name', 'main_author')
    list_display_links = ('id', 'last_name', 'first_name', 'middle_name', 'main_author')

    search_fields = ('id', 'last_name', 'middle_name', 'first_name',)

    autocomplete_fields = ('main_author',)
    list_select_related = ('main_author',)

    # inlines = [FlibustaAuthorInline, ]

    readonly_fields = ('library_author', )

    def get_queryset(self, request):
        # add filter for autocomplete field 'main_author'
        # The author cannot be linked to another author who is already linked to the main author.
        if request.GET.get('field_name') == 'main_author':
            return super().get_queryset(request).filter(main_author=None).select_related('main_author')

        return super().get_queryset(request).select_related('main_author')

    # def get_readonly_fields(self, request, obj=None):
    #     if request.user.is_superuser:
    #         return self.readonly_fields
    #
    #     return self.fields


admin.site.register(FlibustaAuthor, FlibustaAuthorAdmin)
admin.site.register(FlibustaGenre, FlibustaGenreAdmin)
