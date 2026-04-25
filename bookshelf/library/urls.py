from django.urls import path

from library import views

app_name = 'library'

urlpatterns = [
    path('',  views.HomePageView.as_view(), name='home'),
    path('authors/', views.AuthorListView.as_view(), name='authors_list'),
    path('authors/<int:pk>/', views.AuthorDetailView.as_view(), name='author'),
    path('books/', views.BookListView.as_view(), name='book_list'),
    path('books/<int:pk>/', views.BookDetailView.as_view(), name='book'),
    path('books/<int:pk>/chapter/<int:chapter_index>/', views.BookDetailView.as_view(), name='book_chapter'),
    path('books/<int:pk>/download/', views.BookDownloadView.as_view(), name='book_download'),
]