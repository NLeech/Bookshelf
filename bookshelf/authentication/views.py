from django.urls import reverse_lazy
from allauth.account.views import PasswordSetView as allauth_PasswordSetView
from allauth.account.views import PasswordChangeView as allauth_PasswordChangeView


# fix issue : https://github.com/pennersr/django-allauth/issues/2195
class PasswordSetView(allauth_PasswordSetView):
    success_url = reverse_lazy('library:home')


class PasswordChangeView(allauth_PasswordChangeView):
    success_url = reverse_lazy('library:home')
