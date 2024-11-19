from django.contrib import admin
from .models import Category, SupportTicket, SupportTicketStatusChange, SupportTicketMessage


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Category._meta.fields]
    search_fields = ["name"]


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = [field.name for field in SupportTicket._meta.fields]
    search_fields = ["id", "uuid", "booking__uuid"]


@admin.register(SupportTicketStatusChange,)
class SupportTicketStatusChangeAdmin(admin.ModelAdmin):
    list_display = [field.name for field in SupportTicketStatusChange._meta.fields]
    search_fields = ["support_ticket_id", "support_ticket__uuid"]


@admin.register(SupportTicketMessage)
class SupportTicketMessageAdmin(admin.ModelAdmin):
    list_display = [field.name for field in SupportTicketMessage._meta.fields]
    search_fields = ["support_ticket_id", "support_ticket__uuid"]