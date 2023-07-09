from django.contrib import admin
from .models import (CleaningType, Cleaning, CleaningStatusChange,
                     CleanerForCleaning, CleaningChatMessage)


class CleaningStatusChangeInline(admin.TabularInline):
    model = CleaningStatusChange
    extra = 0


@admin.register(Cleaning)
class CleaningAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Cleaning._meta.fields]
    inlines = [CleaningStatusChangeInline]


@admin.register(CleaningStatusChange)
class CleaningStatusChangeAdmin(admin.ModelAdmin):
    list_display = [field.name for field in CleaningStatusChange._meta.fields]


@admin.register(CleanerForCleaning)
class CleanerForCleaningAdmin(admin.ModelAdmin):
    list_display = [field.name for field in CleanerForCleaning._meta.fields]


@admin.register(CleaningChatMessage)
class CleaningChatMessageAdmin(admin.ModelAdmin):
    list_display = [field.name for field in CleaningChatMessage._meta.fields]
    search_fields = ["cleaning__uuid", "user__email"]