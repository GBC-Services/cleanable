from django.contrib import admin
from .models import NotificationTemplate, Notification
from companies.models import Company


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = [field.name for field in NotificationTemplate._meta.fields]
    search_fields = ["name"]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Notification._meta.fields]
    search_fields = ["email", "phone", "cleaning__uuid", "booking__uuid"]
    list_filter = ["template__channel", "template"]
