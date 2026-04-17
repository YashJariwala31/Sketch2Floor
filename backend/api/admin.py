from django.contrib import admin

from .models import FloorplanJob


@admin.register(FloorplanJob)
class FloorplanJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'status', 'original_filename', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'original_filename', 'description')
