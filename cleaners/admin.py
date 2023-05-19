from django.contrib import admin
from .models import ScheduleChange, Schedule


@admin.register(ScheduleChange)
class ScheduleChangeAdmin(admin.ModelAdmin):
    list_display = [field.name for field in ScheduleChange._meta.fields]


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Schedule._meta.fields]