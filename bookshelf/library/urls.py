from django.urls import path

from library import views

app_name = "library"
urlpatterns = [
    path('',  views.HomePageView.as_view(), name='home'),
    path('authors', views.AuthorListView.as_view(), name='authors_list'),
    path('authors/<int:pk>', views.AuthorDetailView.as_view(), name='author_details'),
    path('books/<int:pk>/', views.BookDetailView.as_view(), name='book_details'),
    path('books/<int:pk>/chapter/<int:chapter_index>/', views.BookDetailView.as_view(), name='book_details_chapter'),
]