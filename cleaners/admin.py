from django.contrib import admin
from .models import CompanyCleanerInvite, SchedulePeriod, ScheduleTimeSlot, CleanerSchedule


@admin.register(CompanyCleanerInvite)
class CompanyCleanerInviteAdmin(admin.ModelAdmin):
    list_display = [field.name for field in CompanyCleanerInvite._meta.fields]


@admin.register(SchedulePeriod)
class SchedulePeriodAdmin(admin.ModelAdmin):
    list_display = [field.name for field in SchedulePeriod._meta.fields]


@admin.register(ScheduleTimeSlot)
class ScheduleTimeSlotAdmin(admin.ModelAdmin):
    list_display = [field.name for field in ScheduleTimeSlot._meta.fields]


@admin.register(CleanerSchedule)
class CleanerScheduleAdmin(admin.ModelAdmin):
    list_display = [field.name for field in CleanerSchedule._meta.fields]
    search_fields = ["user__uuid"]
    list_filter = ["is_active"]