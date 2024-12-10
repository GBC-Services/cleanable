from django.contrib import admin
from apps.companies.models import Company, CompanyDocumentType, CompanyDocument, \
    CompanyServiceFeesSnapshot, CompanyServiceFee
from apps.cleaners.models import CompanyCleanerInvite
from django.contrib.auth import get_user_model
UserModel = get_user_model()


class CompanyCleanerInviteInline(admin.TabularInline):
    model = CompanyCleanerInvite
    extra = 0
    fields = ["email", "user"]
    readonly_fields = fields


class CompanyUserInline(admin.TabularInline):
    model = UserModel
    extra = 0
    fields = ["role", "first_name", "last_name", "email", "last_login"]
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


class CompanyServiceFeesSnapshotInline(admin.TabularInline):
    model = CompanyServiceFeesSnapshot
    extra = 0


class CompanyServiceInline(admin.TabularInline):
    model = CompanyServiceFee
    extra = 0


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Company._meta.fields]
    search_fields = ["name", "uuid", "region__name"]
    list_filter = ["region"]
    inlines = [CompanyCleanerInviteInline, CompanyUserInline, CompanyServiceFeesSnapshotInline]


@admin.register(CompanyDocumentType)
class CompanyDocumentTypeAdmin(admin.ModelAdmin):
    list_display = [field.name for field in CompanyDocumentType._meta.fields]
    search_fields = ["uuid", "name"]


@admin.register(CompanyDocument)
class CompanyDocumentAdmin(admin.ModelAdmin):
    list_display = [field.name for field in CompanyDocument._meta.fields]
    search_fields = ["uuid", "type__name"]


@admin.register(CompanyServiceFeesSnapshot)
class CompanyServiceFeesSnapshotAdmin(admin.ModelAdmin):
    list_display = [field.name for field in CompanyServiceFeesSnapshot._meta.fields]
    inlines = [CompanyServiceInline]


@admin.register(CompanyServiceFee)
class CompanyServiceFeeAdmin(admin.ModelAdmin):
    list_display = [field.name for field in CompanyServiceFee._meta.fields]
    search_fields = ["company__name", "company__uuid", "service__name", "service__uuid"]
    list_filter = ["service__cleaning_type__name", "service__regularity_type"]
