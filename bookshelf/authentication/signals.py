from django.contrib.auth import signals
from django.dispatch import receiver
from django.contrib import messages
from django.urls import reverse
from django.utils.safestring import mark_safe


@receiver(signals.user_logged_in)
def send_login_message(sender, request, user, **kwargs):
    # Users without a password can't log in through opds
    if not user.has_usable_password():
        messages.add_message(
            request,
            messages.WARNING,
            mark_safe(f'For using API you have to set your password '
                      f'<a href="{reverse("account_set_password")}">Set password</a>'),
            fail_silently=True,
        )
