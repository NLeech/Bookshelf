from django.urls import path

from . import views

app_name = 'opds'

urlpatterns = [
    path('', views.RootFeedView.as_view(), name='root'),
]
