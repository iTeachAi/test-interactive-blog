from django.urls import path

from django.views.generic import TemplateView

from . import editor
from .editor_stats import EditorStatSheetView

from . import views

urlpatterns = [
    path('editor/', editor.BlogEditorView.as_view(), name='blog-editor'),
    path('editor/stat-analyzer/', EditorStatSheetView.as_view(), name='editor-stat-sheet'),
    path('editor/court-lingo/', editor.CourtTermEditorView.as_view(), name='editor-court-lingo'),
    path('editor/court-lingo/new/', editor.CourtTermCreateView.as_view(), name='editor-term-create'),
    path('editor/court-lingo/<int:pk>/edit/', editor.CourtTermUpdateView.as_view(), name='editor-term-update'),
    path('editor/new/', editor.BlogCreateView.as_view(), name='blog-create'),
    path('editor/<int:pk>/edit/', editor.BlogUpdateView.as_view(), name='blog-update'),
    path('editor/<int:pk>/image/', editor.BlogGenerateImageView.as_view(), name='blog-generate-image'),
    path('editor/<int:pk>/delete/', editor.BlogDeleteView.as_view(), name='blog-delete'),
    path('', views.home, name='home'),
    path('blog/', views.BlogArchiveView.as_view(), name='blog-archive'),
    path('blog/<slug:role>/', views.audience_blog, name='audience-blog'),
    path('posts/<int:pk>/', views.BlogDetailView.as_view(), name='blog-detail'),
    path('posts/<slug:slug>/', views.BlogDetailView.as_view(), name='blog-detail'),
    path('court-lingo/', views.court_lingo, name='court-lingo'),
    path('court-lingo/<slug:slug>/pdf/', views.court_term_pdf, name='court-term-pdf'),
    path('court-lingo/<slug:slug>/', views.term_detail, name='court-term'),
    path('video-lessons/', views.video_lessons, name='video-lessons'),
    path('stat-sheet-analyzer/', views.analyzer, name='stat-analyzer'),
    path('stat-sheet-analyzer/results/', TemplateView.as_view(
        template_name='frontendblog/analyzer.html', extra_context={'results': True},
    ), name='stat-analyzer-results'),
    path('consultation/', views.ConsultationView.as_view(), name='consultation'),
    path('consultation/received/', TemplateView.as_view(
        template_name='frontendblog/consultation.html', extra_context={'received': True},
    ), name='consultation-received'),
]
