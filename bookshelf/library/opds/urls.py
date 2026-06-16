from django.urls import path

from . import views

app_name = 'opds'

urlpatterns = [
    path('', views.RootFeedView.as_view(), name='root'),

    # Author endpoints.
    # The <int:pk> converter never matches the literal segment 'tree', so
    # tree routes and detail routes are unambiguous regardless of order.
    path('authors/', views.AuthorListFeedView.as_view(), name='author_list'),
    path('authors/tree/', views.AuthorTreeFeedView.as_view(), name='author_tree'),
    path('authors/tree/<str:name>/', views.AuthorTreeFeedView.as_view(), name='author_tree_node'),
    path('authors/<int:pk>/', views.AuthorDetailFeedView.as_view(), name='author_detail'),
    path('authors/<int:pk>/series/', views.AuthorSeriesFeedView.as_view(), name='author_series'),
    path('authors/<int:pk>/books/', views.AuthorBooksFeedView.as_view(), name='author_books'),
    path('authors/<int:pk>/books/recent/', views.AuthorRecentBooksFeedView.as_view(), name='author_books_recent'),
]
