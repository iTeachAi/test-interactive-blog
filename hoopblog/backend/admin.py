from django.contrib import admin

from .forms import BlogPostImportForm
from .models import BlogPost


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    fields = ('title', 'category', 'author', 'summary', 'body')
    list_display = ('title', 'category', 'author', 'date')
    list_filter = ('category',)
    search_fields = ('title', 'body')

    def get_fields(self, request, obj=None):
        if obj is None:
            return (*self.fields, 'source_file')
        return self.fields

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs['form'] = BlogPostImportForm
        return super().get_form(request, obj, **kwargs)
