from django.contrib import admin
from companies.models import (Company, CompanyUser, CompanyService,
                              CleaningType, RegularityType, CompanyService)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Company._meta.fields]


@admin.register(CompanyUser)
class CompanyUserAdmin(admin.ModelAdmin):
    list_display = [field.name for field in CompanyUser._meta.fields]


@admin.register(CleaningType)
class CleaningTypeAdmin(admin.ModelAdmin):
    list_display = [field.name for field in CleaningType._meta.fields]


@admin.register(RegularityType)
class RegularityTypeAdmin(admin.ModelAdmin):
    list_display = [field.name for field in RegularityType._meta.fields]


@admin.register(CompanyService)
class CompanyServiceAdmin(admin.ModelAdmin):
    list_display = [field.name for field in CompanyService._meta.fields]

