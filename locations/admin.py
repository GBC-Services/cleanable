from django.contrib import admin
from .models import Country, State, City, Region, ZipCode, RegionZipCode
from companies.models import Company


class CompanyInline(admin.TabularInline):
    model = Company
    extra = 0


class RegionZipCodeInline(admin.TabularInline):
    model = RegionZipCode
    extra = 0


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = [field.name for field in City._meta.fields]


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = [field.name for field in State._meta.fields]


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Country._meta.fields]


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Region._meta.fields]
    inlines = [CompanyInline, RegionZipCodeInline]


@admin.register(ZipCode)
class ZipCodeAdmin(admin.ModelAdmin):
    list_display = [field.name for field in ZipCode._meta.fields]


@admin.register(RegionZipCode)
class RegionZipCodeAdmin(admin.ModelAdmin):
    list_display = [field.name for field in RegionZipCode._meta.fields]