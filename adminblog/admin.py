from django.contrib import admin

from .models import Blog


@admin.register(Blog)
class BlogAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "author",
        "date",
    )
    search_fields = ("name", "summary", "content")
    list_filter = ("category", "date")