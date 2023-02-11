from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.admin import Group as BaseGroup

from authentication.models import User, Group


class UserAdmin(BaseUserAdmin):
    search_fields = ("email", "username")
    ordering = ("username",)

    list_display = ("username", "email", "is_staff")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Permissions", {"fields": (
                "is_active",
                "is_staff",
                "is_superuser",
                "groups",
                "user_permissions"
            )
        }),
        ("Important dates", {"fields": ("last_login", "date_joined")})
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("username", "email", "password1", "password2")}),
    )


admin.site.unregister(BaseGroup)
admin.site.register(User, UserAdmin)
admin.site.register(Group)
