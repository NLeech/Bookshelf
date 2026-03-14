from django.contrib import admin
from .models import (
    FlibustaAuthor, FlibustaGenre, FlibustaSequence,
    FlibustaBook, FlibustaBookAuthor, FlibustaBookGenre,
    FlibustaBookSequence, FlibustaJoinedBook
)


class FlibustaBookAuthorInline(admin.TabularInline):
    model = FlibustaBookAuthor
    extra = 0
    autocomplete_fields = ['author']


class FlibustaBookGenreInline(admin.TabularInline):
    model = FlibustaBookGenre
    extra = 0
    autocomplete_fields = ['genre']


class FlibustaBookSequenceInline(admin.TabularInline):
    model = FlibustaBookSequence
    extra = 0
    autocomplete_fields = ['sequence']


@admin.register(FlibustaAuthor)
class FlibustaAuthorAdmin(admin.ModelAdmin):
    list_display = ('id', 'last_name', 'first_name', 'middle_name', 'nickname', 'uid')
    search_fields = ('id', 'last_name', 'first_name', 'middle_name', 'nickname', 'email')
    list_filter = ('gender',)
    ordering = ('last_name', 'first_name')


@admin.register(FlibustaGenre)
class FlibustaGenreAdmin(admin.ModelAdmin):
    list_display = ('id', 'genre_code', 'genre_desc', 'genre_meta')
    search_fields = ('id', 'genre_code', 'genre_desc', 'genre_meta')
    list_filter = ('genre_meta',)
    ordering = ('genre_code',)


@admin.register(FlibustaSequence)
class FlibustaSequenceAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('id', 'name',)
    ordering = ('name',)


@admin.register(FlibustaBook)
class FlibustaBookAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'lang', 'file_type', 'year', 'deleted')
    search_fields = ('id', 'title', 'title1', 'md5')
    list_filter = ('lang', 'file_type', 'deleted', 'year')
    inlines = [FlibustaBookAuthorInline, FlibustaBookGenreInline, FlibustaBookSequenceInline]
    ordering = ('-id',)


@admin.register(FlibustaJoinedBook)
class FlibustaJoinedBookAdmin(admin.ModelAdmin):
    list_display = ('id', 'bad_id', 'good_id', 'real_id', 'time')
    search_fields = ('bad_id', 'good_id', 'real_id')
    ordering = ('-time',)
