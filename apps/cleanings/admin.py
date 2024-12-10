from django.contrib import admin
from .models import (Cleaning, SpecialCleaningRequest, CleaningInvoice, CleaningStatusChange,
                     CleanerForCleaning, CleaningChatMessage,
                     FeedbackTagForCleaner, FeedbackTagForClient
                     )


class CleaningStatusChangeInline(admin.TabularInline):
    model = CleaningStatusChange
    extra = 0


@admin.register(FeedbackTagForCleaner)
class FeedbackTagForCleanerAdmin(admin.ModelAdmin):
    list_display = [field.name for field in FeedbackTagForCleaner._meta.fields]


@admin.register(FeedbackTagForClient)
class FeedbackTagForClientAdmin(admin.ModelAdmin):
    list_display = [field.name for field in FeedbackTagForClient._meta.fields]


@admin.register(Cleaning)
class CleaningAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Cleaning._meta.fields]
    search_fields = ["uuid", "booking__uuid"]
    inlines = [CleaningStatusChangeInline]


@admin.register(SpecialCleaningRequest)
class SpecialCleaningRequestAdmin(admin.ModelAdmin):
    list_display = [field.name for field in SpecialCleaningRequest._meta.fields]


@admin.register(CleaningInvoice)
class CleaningInvoiceAdmin(admin.ModelAdmin):
    list_display = [field.name for field in CleaningInvoice._meta.fields]


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