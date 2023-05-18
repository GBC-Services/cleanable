from django.contrib import admin
from .models import Cleaner, ScheduleChange, Schedule


@admin.register(Cleaner)
class CleanerAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Cleaner._meta.fields]


@admin.register(ScheduleChange)
class ScheduleChangeAdmin(admin.ModelAdmin):
    list_display = [field.name for field in ScheduleChange._meta.fields]


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Schedule._meta.fields]