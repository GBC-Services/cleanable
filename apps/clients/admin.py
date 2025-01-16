from django.contrib import admin
from .models import Place, MapboxRequest


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Place._meta.fields]
    search_fields = ["region__name"]


admin.register(MapboxRequest)
class MapboxRequestAdmin(admin.ModelAdmin):
    list_display = [field.name for field in MapboxRequest._meta.fields]
    search_fields = ["user__uuid", "user__email"]
