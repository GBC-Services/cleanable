from django.contrib import admin
from .forms import UserCreationForm, UserChangeForm
from .models import User
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from django.contrib import admin
from .models import User, UserSession, VerificationDocumentType, UserVerificationDocument

from import_export.admin import ExportActionModelAdmin
from import_export import resources, fields


class UserResource(resources.ModelResource):
    zip_code = fields.Field(column_name="Zip Codes from clients' places")

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "zip_code"]
        name = "Clients only export"

    def get_queryset(self):
        return self._meta.model.objects.filter(role=User.ROLE_CLIENT)

    def dehydrate_zip_code(self, obj):
        zip_codes = obj.get_places().filter(zip_code__isnull=False).values_list("zip_code__value", flat=True)
        if zip_codes:
            zip_codes = ", ".join(list(zip_codes))
            return zip_codes
        else:
            return ""


class CustomUserAdmin(UserAdmin, ExportActionModelAdmin):
    add_form = UserCreationForm
    form = UserChangeForm
    model = User

    resource_classes = [UserResource]
    list_display = ("email", "role", "company", "is_staff", "is_active", "uuid",
                    "is_contact_by_sms", "is_contact_by_email")
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
        (_("Extra fields"), {"fields": ("role", "company", "phone", "is_contact_by_sms", "is_contact_by_email",
                                        "image")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2", "company", "role", "phone"),
        }),
    )

admin.site.register(User, CustomUserAdmin)


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = [field.name for field in UserSession._meta.fields]


@admin.register(VerificationDocumentType)
class VerificationDocumentTypeAdmin(admin.ModelAdmin):
    list_display = [field.name for field in VerificationDocumentType._meta.fields]


@admin.register(UserVerificationDocument)
class UserVerificationDocumentAdmin(admin.ModelAdmin):
    list_display = [field.name for field in UserVerificationDocument._meta.fields]
