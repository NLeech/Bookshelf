from django.contrib import admin

from library.models import Language, Author, BookSeries, BookSeriesName, Genre, Book

admin.site.register(Language)
admin.site.register(Genre)
admin.site.register(Author)
admin.site.register(BookSeries)
admin.site.register(BookSeriesName)
admin.site.register(Book)


