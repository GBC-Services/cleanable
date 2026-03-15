from django.contrib import admin
from .models import Category, SupportTicket, SupportTicketStatusChange, SupportTicketMessage
from .resolution_models import Complaint, ResolutionAction, AgencyBlacklist, ComplaintNotification


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


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ["id", "uuid", "scenario", "status", "urgency", "resident", "company", "created"]
    list_filter = ["scenario", "status", "urgency"]
    search_fields = ["id", "uuid", "description", "resident__email"]
    raw_id_fields = ["resident", "booking", "cleaning", "company", "assigned_to", "support_ticket"]


@admin.register(ResolutionAction)
class ResolutionActionAdmin(admin.ModelAdmin):
    list_display = ["id", "uuid", "action_type", "execution_status", "performed_by", "complaint", "created"]
    list_filter = ["action_type", "execution_status"]
    search_fields = ["id", "uuid", "notes"]
    raw_id_fields = ["complaint", "performed_by", "redo_cleaning", "redo_assigned_company", "blacklisted_company"]


@admin.register(AgencyBlacklist)
class AgencyBlacklistAdmin(admin.ModelAdmin):
    list_display = ["id", "uuid", "resident", "company", "blacklisted_at"]
    search_fields = ["resident__email", "company__name"]
    raw_id_fields = ["resident", "company", "complaint"]


@admin.register(ComplaintNotification)
class ComplaintNotificationAdmin(admin.ModelAdmin):
    list_display = ["id", "channel", "status", "recipient", "complaint", "sent_at"]
    list_filter = ["channel", "status"]
    search_fields = ["recipient__email", "message_body"]
    raw_id_fields = ["complaint", "resolution_action", "recipient"]