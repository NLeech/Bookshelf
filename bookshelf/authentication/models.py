from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import Group as BaseGroup


class LowerEmailField(models.EmailField):
    def get_prep_value(self, value):
        return value.lower()


class User(AbstractUser):
    email = LowerEmailField(unique=True)
    username = models.CharField(max_length=50, unique=True)

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"

    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return self.email


class Group(BaseGroup):
    """A proxy groups model for inclusion in admin site with the custom user model."""

    class Meta:
        proxy = True
