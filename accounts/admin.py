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

    # Champs visibles à l'édition d'un user
    fieldsets = (
        (None, {"fields": ("username", "email", "role", "password")}),
        (_("Permissions"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )

    # Champs visibles à la création d'un user
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "role", "password1", "password2"),
        }),
    )
