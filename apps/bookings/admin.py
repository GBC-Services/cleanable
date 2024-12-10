from django.contrib import admin
from .models import (DiscountCode, Booking, BookingStatusChange, BookingService, BookingChatMessage)


class BookingServiceInline(admin.TabularInline):
    model = BookingService
    extra = 0


@admin.register(DiscountCode)
class DiscountCodeAdmin(admin.ModelAdmin):
    list_display = [field.name for field in DiscountCode._meta.fields]


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Booking._meta.fields]
    inlines = [BookingServiceInline]
    search_fields = ["user__email"]


@admin.register(BookingStatusChange)
class BookingStatusChangeAdmin(admin.ModelAdmin):
    list_display = [field.name for field in BookingStatusChange._meta.fields]


@admin.register(BookingService)
class BookingServiceAdmin(admin.ModelAdmin):
    list_display = [field.name for field in BookingService._meta.fields]


@admin.register(BookingChatMessage)
class BookingChatMessageAdmin(admin.ModelAdmin):
    list_display = [field.name for field in BookingChatMessage._meta.fields]
    search_fields = ["booking__uuid", "user__email"]