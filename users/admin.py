from django.contrib import admin
from .forms import UserCreationForm, UserChangeForm
from .models import User
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from django.contrib import admin
from .models import User, UserSession


class CustomUserAdmin(UserAdmin):
    add_form = UserCreationForm
    form = UserChangeForm
    model = User

    list_display = ("email", "role", "company", "is_staff", "is_active", "uuid",)
    list_filter = ("role", "is_staff", "is_active",)
    search_fields = ("email", "first_name", "last_name", "uuid",)
    ordering = ("email",)

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name",)}),
        (_("Permissions"), {
            "fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions",),
        }),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
        (_("Extra fields"), {"fields": ("role", "company")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2", "company", "role"),
        }),
    )

admin.site.register(User, CustomUserAdmin)


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = [field.name for field in UserSession._meta.fields]