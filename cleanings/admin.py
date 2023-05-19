from django.contrib import admin
from .models import (CleaningType, RegularityType, CleaningRequest, CleaningStatus,
                     FeedbackTagForCleaner, FeedbackTagForClient, Cleaning, AddOn, CleaningAddOn)


@admin.register(CleaningType)
class CleaningTypeAdmin(admin.ModelAdmin):
    list_display = [field.name for field in CleaningType._meta.fields]


@admin.register(RegularityType)
class RegularityTypeAdmin(admin.ModelAdmin):
    list_display = [field.name for field in RegularityType._meta.fields]


@admin.register(CleaningRequest)
class CleaningRequestAdmin(admin.ModelAdmin):
    list_display = [field.name for field in CleaningRequest._meta.fields]


@admin.register(CleaningStatus)
class CleaningStatusAdmin(admin.ModelAdmin):
    list_display = [field.name for field in CleaningStatus._meta.fields]


@admin.register(FeedbackTagForCleaner)
class FeedbackTagForCleanerAdmin(admin.ModelAdmin):
    list_display = [field.name for field in FeedbackTagForCleaner._meta.fields]


@admin.register(FeedbackTagForClient)
class FeedbackTagForClientAdmin(admin.ModelAdmin):
    list_display = [field.name for field in FeedbackTagForClient._meta.fields]


@admin.register(Cleaning)
class CleaningAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Cleaning._meta.fields]


@admin.register(AddOn)
class AddOnAdmin(admin.ModelAdmin):
    list_display = [field.name for field in AddOn._meta.fields]


@admin.register(CleaningAddOn)
class CleaningAddOnAdmin(admin.ModelAdmin):
    list_display = [field.name for field in CleaningAddOn._meta.fields]