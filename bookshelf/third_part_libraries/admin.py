from django.contrib import admin

from third_part_libraries.models import FlibustaAuthor


class FlibustaAuthorAdmin(admin.ModelAdmin):
    # fields = ("title", "text", "tags")
    list_display = ('id', 'last_name', 'first_name', 'middle_name', 'main_author')
    list_display_links = list_display
    search_fields = ('id', 'last_name', 'middle_name', 'first_name',)


admin.site.register(FlibustaAuthor, FlibustaAuthorAdmin)
