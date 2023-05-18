from django.contrib import admin
from .models import Client, PlaceType, Place


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Client._meta.fields]


@admin.register(PlaceType)
class PlaceTypeAdmin(admin.ModelAdmin):
    list_display = [field.name for field in PlaceType._meta.fields]


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Place._meta.fields]