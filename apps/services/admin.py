from django.contrib import admin
from .models import (CleaningType, Service, ApartmentPlan,
                     ServiceFeesSnapshot, ServiceFee)


class ServiceFeeInline(admin.TabularInline):
    model = ServiceFee
    extra = 0


@admin.register(CleaningType)
class CleaningTypeAdmin(admin.ModelAdmin):
    list_display = [field.name for field in CleaningType._meta.fields]


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Service._meta.fields]


@admin.register(ApartmentPlan)
class ApartmentPlanAdmin(admin.ModelAdmin):
    list_display = [field.name for field in ApartmentPlan._meta.fields]


@admin.register(ServiceFeesSnapshot)
class ServiceFeesSnapshotAdmin(admin.ModelAdmin):
    list_display = [field.name for field in ServiceFeesSnapshot._meta.fields]
    inlines = [ServiceFeeInline]


@admin.register(ServiceFee)
class ServiceFeeAdmin(admin.ModelAdmin):
    list_display = [field.name for field in ServiceFee._meta.fields]