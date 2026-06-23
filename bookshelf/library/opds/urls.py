from django.urls import path

from . import views

app_name = 'opds'

urlpatterns = [
    path('', views.RootFeedView.as_view(), name='root'),
    path('login/', views.OPDSLoginView.as_view(), name='login'),

    # Author endpoints.
    path('authors/', views.AuthorListFeedView.as_view(), name='author_list'),
    path('authors/tree/', views.AuthorTreeFeedView.as_view(), name='author_tree'),
    path('authors/tree/<str:name>/', views.AuthorTreeFeedView.as_view(), name='author_tree_node'),
    path('authors/<int:pk>/', views.AuthorDetailFeedView.as_view(), name='author_detail'),
    path('authors/<int:pk>/series/', views.AuthorSeriesFeedView.as_view(), name='author_series'),
    path('authors/<int:pk>/books/', views.AuthorBooksFeedView.as_view(), name='author_books'),
    path('authors/<int:pk>/books/recent/', views.AuthorRecentBooksFeedView.as_view(), name='author_books_recent'),

    # Genre endpoints.
    path('genres/', views.GenreRootFeedView.as_view(), name='genres'),
    path('genres/<int:pk>/', views.GenreDetailFeedView.as_view(), name='genre_detail'),
    path('genres/<int:pk>/books/tree/', views.GenreBookTreeFeedView.as_view(), name='genre_book_tree'),
    path('genres/<int:pk>/books/tree/<str:name>/', views.GenreBookTreeFeedView.as_view(), name='genre_book_tree_node'),
    path('genres/<int:pk>/books/', views.GenreBookListFeedView.as_view(), name='genre_book_list'),

    # Series endpoints.
    path('series/', views.SeriesListFeedView.as_view(), name='series_list'),
    path('series/tree/', views.SeriesTreeFeedView.as_view(), name='series_tree'),
    path('series/tree/<str:name>/', views.SeriesTreeFeedView.as_view(), name='series_tree_node'),
    path('series/<int:pk>/', views.SeriesDetailFeedView.as_view(), name='series_detail'),

    # Book endpoints.
    path('books/', views.BookListFeedView.as_view(), name='book_list'),
    path('books/tree/', views.BookTreeFeedView.as_view(), name='book_tree'),
    path('books/tree/<str:name>/', views.BookTreeFeedView.as_view(), name='book_tree_node'),
    path('books/<int:pk>/', views.BookDetailFeedView.as_view(), name='book_detail'),
    path('books/<int:pk>/download/', views.OPDSBookDownloadView.as_view(), name='book_download'),

    # Search endpoints.
    path('search/', views.SearchRootFeedView.as_view(), name='search'),
    path('search/authors/', views.SearchAuthorsFeedView.as_view(), name='search_authors'),
    path('search/series/', views.SearchSeriesFeedView.as_view(), name='search_series'),
    path('search/books/', views.SearchBooksFeedView.as_view(), name='search_books'),
    path('search/description.xml', views.OpenSearchDescriptionView.as_view(), name='opensearch_description'),
]
