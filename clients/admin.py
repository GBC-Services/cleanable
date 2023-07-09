from django.contrib import admin
from .models import Place


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Place._meta.fields]
    search_fields = ["region__name"]