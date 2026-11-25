from django.contrib import admin
from django.db import models

from .forms import BlogPostImportForm, CourtTermPDFInput
from .models import BlogPost, ConsultationRequest, CourtTerm, VideoLesson


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    fields = ('title', 'category', 'author', 'summary', 'body', 'audiences', 'topics', 'status', 'date')
    list_display = ('title', 'category', 'author', 'status', 'date')
    list_filter = ('category', 'audiences', 'status')
    search_fields = ('title', 'body')

    def get_fields(self, request, obj=None):
        if obj is None:
            return (*self.fields, 'source_file')
        return self.fields

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs['form'] = BlogPostImportForm
        return super().get_form(request, obj, **kwargs)


@admin.register(CourtTerm)
class CourtTermAdmin(admin.ModelAdmin):
    formfield_overrides = {models.FileField: {'widget': CourtTermPDFInput}}
admin.site.register(VideoLesson)


@admin.register(ConsultationRequest)
class ConsultationRequestAdmin(admin.ModelAdmin):
    list_display = ('name', 'role', 'submitted_at')
    search_fields = ('name', 'email')
    readonly_fields = ('name', 'email', 'role', 'question', 'submitted_at')

    def has_add_permission(self, request):
        return False
