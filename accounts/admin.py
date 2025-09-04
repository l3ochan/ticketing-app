# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User

@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    # Colonnes listées
    list_display = ("username", "email", "role", "is_staff", "is_active")
    search_fields = ("username", "email")
    ordering = ("username",)

    # Écrans d'édition d'un user existant
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "role", "password1", "password2"),
        }),
    )

    # Écran de création d’un user (hash automatique via password1/password2)
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "role", "password1", "password2"),
        }),
    )
